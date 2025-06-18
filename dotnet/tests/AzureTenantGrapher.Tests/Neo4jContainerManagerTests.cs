using System;
using AzureTenantGrapher.Container;
using Microsoft.Extensions.Logging;
using Moq;
using Xunit;

namespace AzureTenantGrapher.Tests
{
    public class Neo4jContainerManagerTests
    {
        [Fact]
        public void SetupNeo4j_ThrowsWhenDockerMissing()
        {
            // Arrange
            var loggerMock = new Mock<ILogger<Neo4jContainerManager>>();
            var manager = new Neo4jContainerManager(loggerMock.Object);

            var original = Environment.GetEnvironmentVariable("DOCKER_PRESENT");
            Environment.SetEnvironmentVariable("DOCKER_PRESENT", null);

            try
            {
                // Act & Assert
                Assert.Throws<InvalidOperationException>(() => manager.SetupNeo4j(2));
            }
            finally
            {
                Environment.SetEnvironmentVariable("DOCKER_PRESENT", original);
            }
        }

        [Fact]
        public void SetupNeo4j_SucceedsWhenDockerPresent()
        {
            // Arrange
            var loggerMock = new Mock<ILogger<Neo4jContainerManager>>();
            var manager = new Neo4jContainerManager(loggerMock.Object);

            var original = Environment.GetEnvironmentVariable("DOCKER_PRESENT");
            Environment.SetEnvironmentVariable("DOCKER_PRESENT", "true");

            try
            {
                // Act & Assert
                manager.SetupNeo4j(2); // Should not throw
            }
            finally
            {
                Environment.SetEnvironmentVariable("DOCKER_PRESENT", original);
            }
        }
    }
}