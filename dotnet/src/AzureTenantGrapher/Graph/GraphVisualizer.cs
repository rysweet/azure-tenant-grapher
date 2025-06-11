using System;
using System.IO;
using System.Threading.Tasks;
using Neo4j.Driver;
using Newtonsoft.Json;
using System.Collections.Generic;

namespace AzureTenantGrapher.Graph
{
    public class GraphVisualizer
    {
        private readonly IDriver _driver;

        public GraphVisualizer(string uri, string user, string password)
        {
            _driver = GraphDatabase.Driver(uri, AuthTokens.Basic(user, password));
        }

        public string GenerateHtmlVisualization(string? outputPath)
        {
            var data = ExtractGraphDataAsync().GetAwaiter().GetResult();
            var json = JsonConvert.SerializeObject(data);
            var html = $"<html><head><meta charset=\"utf-8\"></head><body>" +
                       "<div id=\"3d-graph\"></div>" +
                       $"<script>const graphData = {json};</script>" +
                       "<script src=\"https://unpkg.com/3d-force-graph\"></script>" +
                       "<script>const Graph = ForceGraph3D()(document.getElementById('3d-graph')).graphData(graphData);</script>" +
                       "</body></html>";
            var path = outputPath ?? "visualization.html";
            File.WriteAllText(path, html);
            return path;
        }

        private async Task<object> ExtractGraphDataAsync()
        {
            var nodes = new List<object>();
            var links = new List<object>();

            await using var session = _driver.AsyncSession();
            var nodeResult = await session.RunAsync(
                "MATCH (n) RETURN id(n) AS id, labels(n) AS labels, properties(n) AS props");
            await nodeResult.ForEachAsync(record =>
            {
                nodes.Add(new
                {
                    id = record["id"].As<long>(),
                    group = record["labels"].As<List<string>>()[0],
                    properties = record["props"].As<IDictionary<string, object>>()
                });
            });

            var relResult = await session.RunAsync(
                "MATCH (a)-[r]->(b) RETURN id(a) AS source, id(b) AS target, type(r) AS type");
            await relResult.ForEachAsync(record =>
            {
                links.Add(new
                {
                    source = record["source"].As<long>(),
                    target = record["target"].As<long>(),
                    type = record["type"].As<string>()
                });
            });

            return new { nodes, links };
        }

        public void Close()
        {
            _driver?.Dispose();
        }
    }
}
