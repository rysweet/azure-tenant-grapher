using System;
using AzureTenantGrapher.Graph;
using Xunit;

namespace AzureTenantGrapher.Tests
{
    public class GraphVisualizerTests
    {
        [Fact]
        public void Init_SetsDriver()
        {
            var gv = new GraphVisualizer("bolt://localhost:7687", "neo4j", "pass");
            Assert.NotNull(gv);
        }
    }
}
