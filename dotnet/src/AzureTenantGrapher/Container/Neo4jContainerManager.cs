using System;
using System.Diagnostics;
using System.Threading;

namespace AzureTenantGrapher.Container
{
    public class Neo4jContainerManager
    {
        private const string ComposeFile = "docker-compose.yml";

        public bool SetupNeo4j(int timeoutSeconds = 120)
        {
            if (!IsDockerInstalled()) throw new InvalidOperationException("Docker not found");
            ExecuteCommand($"-f {ComposeFile} up -d");
            return WaitForReady(timeoutSeconds);
        }

        public void StopContainer()
        {
            ExecuteCommand($"-f {ComposeFile} down");
        }

        private void ExecuteCommand(string args)
        {
            var psi = new ProcessStartInfo("docker-compose", args)
            {
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };
            using var p = Process.Start(psi);
            p.WaitForExit();
            if (p.ExitCode != 0) throw new InvalidOperationException($"docker-compose {args} failed");
        }

        private bool WaitForReady(int timeoutSeconds)
        {
            var end = DateTime.UtcNow.AddSeconds(timeoutSeconds);
            while (DateTime.UtcNow < end)
            {
                try
                {
                    // Try simple HTTP health check
                    using var client = new System.Net.Http.HttpClient();
                    var res = client.GetAsync("http://localhost:7474").Result;
                    if (res.IsSuccessStatusCode) return true;
                }
                catch { }
                Thread.Sleep(2000);
            }
            return false;
        }

        private bool IsDockerInstalled()
        {
            return Process.GetProcessesByName("docker").Length > 0;
        }
    }
}
