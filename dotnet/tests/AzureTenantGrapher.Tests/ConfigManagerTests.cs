using System;
using AzureTenantGrapher.Config;
using Xunit;

namespace AzureTenantGrapher.Tests
{
    public class ConfigManagerTests
    {
        [Fact]
        public void CreateConfigFromArgs_MinimumArgs_UsesDefaults()
        {
            // Arrange
            var args = new[] { "--tenantId", "tenant123" };

            // Act
            var config = ConfigManager.CreateConfigFromArgs(args);

            // Assert
            Assert.Equal("tenant123", config.TenantId);
            Assert.False(config.NoContainer);
            Assert.False(config.ContainerOnly);
            Assert.False(config.Visualize);
            Assert.True(config.AutoStopContainer);
            Assert.Equal(0, config.Processing.ResourceLimit);
            Assert.Equal(5, config.Processing.BatchSize);
            Assert.NotNull(config.Neo4j);
            Assert.Equal("bolt://localhost:7687", config.Neo4j.Uri);
            Assert.Equal("neo4j", config.Neo4j.Username);
            Assert.Equal(string.Empty, config.Neo4j.Password);
        }

        [Fact]
        public void CreateConfigFromArgs_AllArgs_ParsesCorrectly()
        {
            // Arrange
            var args = new[]
            {
                "--tenantId", "t1",
                "--noContainer", "true",
                "--containerOnly", "true",
                "--visualize", "true",
                "--skipAutoStop", "true",
                "--resourceLimit", "10",
                "--batchSize", "20",
                "--logLevel", "Debug",
                "--visualizationPath", "out.html",
                "--NEO4J_URI", "bolt://other:7687",
                "--NEO4J_USER", "user",
                "--NEO4J_PASSWORD", "pass"
            };

            // Act
            var config = ConfigManager.CreateConfigFromArgs(args);

            // Assert
            Assert.Equal("t1", config.TenantId);
            Assert.True(config.NoContainer);
            Assert.True(config.ContainerOnly);
            Assert.True(config.Visualize);
            Assert.Equal(10, config.Processing.ResourceLimit);
            Assert.Equal(20, config.Processing.BatchSize);
            Assert.Equal("Debug", config.Logging.LogLevel);
            Assert.Equal("out.html", config.VisualizationPath);
            Assert.Equal("bolt://other:7687", config.Neo4j.Uri);
            Assert.Equal("user", config.Neo4j.Username);
            Assert.Equal("pass", config.Neo4j.Password);
        }
    }
}
