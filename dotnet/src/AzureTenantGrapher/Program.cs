using System;
using System.Threading.Tasks;
using AzureTenantGrapher.Config;
using AzureTenantGrapher.Container;
using AzureTenantGrapher.Graph;
using AzureTenantGrapher.Processing;
using AzureTenantGrapher.Llm;

namespace AzureTenantGrapher
{
    class Program
    {
        static async Task Main(string[] args)
        {
            var config = ConfigManager.CreateConfigFromArgs(args);
            Logging.SetupLogging(config.Logging);

            var containerManager = new Neo4jContainerManager();
            if (!config.NoContainer)
            {
                containerManager.StartContainer();
            }

            if (!config.ContainerOnly)
            {
                var grapher = new AzureTenantGrapher(config);
                await grapher.RunAsync();

                if (config.Visualize)
                {
                    var visualizer = new GraphVisualizer(config.Neo4j.Uri, config.Neo4j.Username, config.Neo4j.Password);
                    visualizer.GenerateHtmlVisualization(config.VisualizationPath);
                }
            }

            if (!config.NoContainer && config.AutoStopContainer)
            {
                containerManager.StopContainer();
            }
        }
    }
}
