using System;
using System.Diagnostics;
using System.IO;
using Xunit;

namespace AzureTenantGrapher.Tests
{
    public class E2eBackupTests
    {
        [Fact]
        public void BackupNeo4j_ShouldLogBackup()
        {
            // Determine project directory based on test assembly location
            var baseDir = AppContext.BaseDirectory;
            var repoRoot = Path.GetFullPath(Path.Combine(baseDir, "../../../../../../"));
            var projectDir = Path.Combine(repoRoot, "dotnet", "src", "AzureTenantGrapher");

            // Prepare backup path
            var backupFile = Path.Combine(Path.GetTempPath(), $"neo4j-backup-{Guid.NewGuid():N}.dump");

            var startInfo = new ProcessStartInfo
            {
                FileName = "dotnet",
                Arguments = $"run -- --backupNeo4j \"{backupFile}\"",
                WorkingDirectory = projectDir,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            using var process = Process.Start(startInfo);
            Assert.NotNull(process);

            bool exited = process.WaitForExit(60000);
            Assert.True(exited, "Process did not exit within timeout.");

            var output = process.StandardOutput.ReadToEnd();

            Assert.Equal(0, process.ExitCode);
            Assert.Contains("Backing up Neo4j database to", output);
            Assert.Contains("Backup completed at", output);
        }
    }
}
