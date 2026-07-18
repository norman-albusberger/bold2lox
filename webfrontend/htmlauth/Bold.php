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
     * Save settings (recursively merged so nested
     * defaults are preserved).
     */
    public function saveSettings(array $newSettings): bool
    {
        $merged = array_replace_recursive($this->readSettings(), $newSettings);
        $result = file_put_contents(
            $this->settingsPath,
            json_encode($merged, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)
        );
        return $result !== false;
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
