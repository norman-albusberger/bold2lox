<?php

error_reporting(E_ALL);
ini_set('display_errors', 1);

/**
 * bold2lox – helper around settings.json and the Python engine.
 */
class Bold
{
    private string $settingsPath;
    private string $enginePath;

    public function __construct(
        ?string $settingsPath = null,
        ?string $enginePath = null
    ) {
        // LBPDATADIR / LBPBINDIR are set by LoxBerry and point to the plugin
        // folders (…/data/plugins/bold2lox and …/bin/plugins/bold2lox).
        $this->settingsPath = $settingsPath ?? (LBPDATADIR . "/settings.json");
        $this->enginePath   = $enginePath ?? (LBPBINDIR . "/bold_engine.py");
    }

    public function settingsPath(): string
    {
        return $this->settingsPath;
    }

    public function readSettings(): array
    {
        if (!file_exists($this->settingsPath)) {
            return [];
        }
        return json_decode(file_get_contents($this->settingsPath), true) ?? [];
    }

    /**
     * Keys only the engine writes (login + refresh). Bold rotates the refresh token
     * on every refresh, so any copy that went through a browser form is stale by
     * definition, and writing it back locks the plugin out (InvalidRefreshToken).
     */
    private const ENGINE_OWNED_BOLD_KEYS = [
        'client_id', 'client_secret', 'refresh_token',
        'access_token', 'access_token_expiry', 'account_id',
        'token_refreshed_at', 'relogin_required', 'last_error', 'last_error_at',
    ];

    /**
     * Last $max lines of auth.log (token events written by the engine), newest first.
     *
     * @return string[]
     */
    public function authLog(int $max = 30): array
    {
        $path = dirname($this->settingsPath) . '/auth.log';
        if (!is_readable($path)) {
            return [];
        }
        $lines = file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: [];
        return array_reverse(array_slice($lines, -$max));
    }

    /**
     * Save settings (recursively merged so nested defaults are preserved).
     *
     * Holds the same lock as bold_engine.py (settings.json.lock, flock(2) on both
     * sides) and re-reads the file inside it, so a token the engine just rotated is
     * never overwritten. Written atomically via a temp file; keeps mode 0600 because
     * the file holds tokens.
     */
    public function saveSettings(array $newSettings): bool
    {
        foreach (self::ENGINE_OWNED_BOLD_KEYS as $key) {
            unset($newSettings['bold'][$key]);
        }

        $lock = fopen($this->settingsPath . '.lock', 'c');
        if ($lock === false || !flock($lock, LOCK_EX)) {
            return false;
        }
        try {
            $current = [];
            if (file_exists($this->settingsPath)) {
                $current = json_decode(file_get_contents($this->settingsPath), true);
                if (!is_array($current)) {
                    // Unreadable file: refuse rather than replace it with one that
                    // has no tokens.
                    return false;
                }
            }
            $merged = array_replace_recursive($current, $newSettings);

            $tmp = $this->settingsPath . '.tmp';
            $json = json_encode($merged, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
            if ($json === false || file_put_contents($tmp, $json) === false) {
                return false;
            }
            chmod($tmp, 0600);
            return rename($tmp, $this->settingsPath);
        } finally {
            flock($lock, LOCK_UN);
            fclose($lock);
        }
    }

    /**
     * Ruft den Python-Engine mit gesetztem Settings-Pfad auf.
     *
     * @return array{returnCode:int, output:string}
     */
    public function runEngine(string $args): array
    {
        $cmd = 'BOLD2LOX_SETTINGS=' . escapeshellarg($this->settingsPath)
            . ' /usr/bin/python3 ' . escapeshellarg($this->enginePath)
            . ' ' . $args . ' 2>&1';
        $output = [];
        $returnCode = 0;
        exec($cmd, $output, $returnCode);
        return ["returnCode" => $returnCode, "output" => implode("\n", $output)];
    }

    /**
     * Query the device list from the Bold cloud (needs a valid token).
     *
     * @return array Liste von ["id"=>..,"name"=>..,"gatewayId"=>..]
     */
    public function discover(): array
    {
        $res = $this->runEngine("discover --json");
        $data = json_decode($res["output"], true);
        return is_array($data) && isset($data["devices"]) ? $data["devices"] : [];
    }

    /**
     * Call the engine with a JSON payload via stdin (for the login –
     * so credentials don't end up in the process list).
     *
     * @return array{returnCode:int, output:string, stderr:string}
     */
    public function runEngineStdin(string $action, array $payload): array
    {
        $cmd = 'BOLD2LOX_SETTINGS=' . escapeshellarg($this->settingsPath)
            . ' /usr/bin/python3 ' . escapeshellarg($this->enginePath)
            . ' ' . escapeshellarg($action);
        $descriptors = [
            0 => ["pipe", "r"],
            1 => ["pipe", "w"],
            2 => ["pipe", "w"],
        ];
        $proc = proc_open($cmd, $descriptors, $pipes);
        if (!is_resource($proc)) {
            return ["returnCode" => 1, "output" => "", "stderr" => "proc_open failed"];
        }
        fwrite($pipes[0], json_encode($payload));
        fclose($pipes[0]);
        $out = stream_get_contents($pipes[1]);
        fclose($pipes[1]);
        $err = stream_get_contents($pipes[2]);
        fclose($pipes[2]);
        $rc = proc_close($proc);
        return ["returnCode" => $rc, "output" => trim($out), "stderr" => trim($err)];
    }

    public function restartService(string $serviceName = "bold2lox.service"): array
    {
        $output = [];
        $returnCode = 0;
        exec("sudo systemctl restart " . escapeshellarg($serviceName), $output, $returnCode);
        return [
            "returnCode" => $returnCode,
            "output" => $output,
            "success" => $returnCode === 0,
        ];
    }
}
