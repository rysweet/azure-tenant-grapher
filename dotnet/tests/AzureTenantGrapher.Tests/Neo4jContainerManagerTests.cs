using System;
using AzureTenantGrapher.Container;
using Xunit;

namespace AzureTenantGrapher.Tests
{
    public class Neo4jContainerManagerTests
    {
        [Fact]
        public void SetupNeo4j_WithInvalidDocker_Throws()
        {
            var mgr = new Neo4jContainerManager();
            // Assuming docker not installed returns exception
            Assert.Throws<InvalidOperationException>(() => mgr.SetupNeo4j(1));
        }
    }
}
