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

       /// <summary>
       /// Generates an interactive 3D graph visualization as HTML.
       /// Includes minimal UI controls for zoom-in/zoom-out (top-left) for discoverability.
       /// Zoom buttons call Three.js OrbitControls dollyIn/dollyOut or move camera if unavailable.
       /// </summary>
       public string GenerateHtmlVisualization(string? outputPath)
       {
           var data = ExtractGraphDataAsync().GetAwaiter().GetResult();
           var json = JsonConvert.SerializeObject(data);
           // Add zoom controls and minimal CSS for top-left positioning.
           // The zoom buttons call the ForceGraph3D camera's dollyIn/dollyOut (if OrbitControls) or adjust camera position.
           // UI is intentionally minimal and non-intrusive.
           var html = @"<html>
<head>
 <meta charset=""utf-8"">
 <style>
   .controls {
     position: absolute;
     top: 12px;
     left: 12px;
     z-index: 10;
     display: flex;
     flex-direction: column;
     gap: 6px;
     background: rgba(255,255,255,0.85);
     border-radius: 6px;
     padding: 6px 8px;
     box-shadow: 0 2px 8px rgba(0,0,0,0.07);
     font-family: sans-serif;
     font-size: 15px;
     user-select: none;
   }
   .controls button {
     margin: 0;
     padding: 2px 10px;
     border: 1px solid #bbb;
     background: #f8f8f8;
     border-radius: 4px;
     cursor: pointer;
     font-size: 18px;
     transition: background 0.15s;
   }
   .controls button:hover {
     background: #e0e0e0;
   }
   #3d-graph {
     width: 100vw;
     height: 100vh;
     min-height: 500px;
     position: relative;
   }
 </style>
</head>
<body>
 <div class=""controls"">
   <!-- Zoom controls: see README for details -->
   <button id=""zoomInBtn"" title=""Zoom In"">＋ Zoom</button>
   <button id=""zoomOutBtn"" title=""Zoom Out"">− Zoom</button>
 </div>
 <div id=""3d-graph""></div>
 <script>const graphData = " + json + @";</script>
 <script src=""https://unpkg.com/3d-force-graph""></script>
 <script>
   // Create the ForceGraph3D instance
   const Graph = ForceGraph3D()(document.getElementById('3d-graph')).graphData(graphData);

   // Wait for the graph to initialize and then wire up zoom controls
   setTimeout(() => {
     // Try to access the Three.js camera and controls
     const threeRenderer = Graph.renderer();
     const threeCamera = Graph.camera();
     const controls = Graph.controls && Graph.controls();

     // Zoom In handler
     document.getElementById('zoomInBtn').onclick = function() {
       if (controls && typeof controls.dollyIn === 'function') {
         controls.dollyIn(1.2); // OrbitControls (Three.js)
         controls.update();
       } else if (threeCamera && threeCamera.position) {
         // Move camera closer for fallback
         threeCamera.position.multiplyScalar(0.8);
       }
     };
     // Zoom Out handler
     document.getElementById('zoomOutBtn').onclick = function() {
       if (controls && typeof controls.dollyOut === 'function') {
         controls.dollyOut(1.2);
         controls.update();
       } else if (threeCamera && threeCamera.position) {
         threeCamera.position.multiplyScalar(1.2);
       }
     };
   }, 500); // Delay to ensure graph is initialized

   // (Other controls, e.g. rotation toggle, are preserved if present)
 </script>
</body>
</html>";
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
