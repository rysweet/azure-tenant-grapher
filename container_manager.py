"""
Container orchestration module for managing Neo4j Docker container.
"""

import subprocess
import time
import logging
import os
from typing import Optional
import docker
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

logger = logging.getLogger(__name__)


class Neo4jContainerManager:
    """Manages Neo4j Docker container lifecycle."""
    
    def __init__(self, compose_file: str = "docker-compose.yml"):
        """
        Initialize the container manager.
        
        Args:
            compose_file: Path to docker-compose.yml file
        """
        self.compose_file = compose_file
        self.docker_client = None
        self.neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        self.neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
        self.neo4j_password = os.getenv('NEO4J_PASSWORD', 'azure-grapher-2024')
        
        try:
            self.docker_client = docker.from_env()
        except Exception as e:
            logger.warning(f"Could not connect to Docker daemon: {e}")
    
    def is_docker_available(self) -> bool:
        """Check if Docker is available and running."""
        try:
            if self.docker_client:
                self.docker_client.ping()
                return True
        except Exception as e:
            logger.error(f"Docker is not available: {e}")
            logger.error("Please ensure Docker Desktop is installed and running.")
            logger.error("You can download Docker Desktop from: https://www.docker.com/products/docker-desktop")
        return False
    
    def is_compose_available(self) -> bool:
        """Check if docker-compose is available."""
        try:
            result = subprocess.run(['docker-compose', '--version'], 
                                  capture_output=True, text=True, check=True)
            logger.info(f"Docker Compose available: {result.stdout.strip()}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            try:
                # Try docker compose (newer syntax)
                result = subprocess.run(['docker', 'compose', 'version'], 
                                      capture_output=True, text=True, check=True)
                logger.info(f"Docker Compose available: {result.stdout.strip()}")
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.error("Docker Compose is not available")
                return False
    
    def get_compose_command(self) -> list:
        """Get the appropriate docker compose command."""
        try:
            subprocess.run(['docker-compose', '--version'], 
                          capture_output=True, check=True)
            return ['docker-compose']
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ['docker', 'compose']
    
    def is_neo4j_container_running(self) -> bool:
        """Check if Neo4j container is running."""
        if not self.docker_client:
            return False
            
        try:
            containers = self.docker_client.containers.list(
                filters={"name": "azure-tenant-grapher-neo4j"}
            )
            return len(containers) > 0 and containers[0].status == 'running'
        except Exception as e:
            logger.error(f"Error checking container status: {e}")
            return False
    
    def start_neo4j_container(self) -> bool:
        """Start Neo4j container using docker-compose."""
        if not self.is_docker_available():
            logger.error("Docker is not available")
            return False
            
        if not self.is_compose_available():
            logger.error("Docker Compose is not available")
            return False
        
        if self.is_neo4j_container_running():
            logger.info("Neo4j container is already running")
            return True
        
        try:
            compose_cmd = self.get_compose_command()
            logger.info("Starting Neo4j container...")
            
            # Start the container
            result = subprocess.run(
                compose_cmd + ['-f', self.compose_file, 'up', '-d', 'neo4j'],
                capture_output=True, text=True, check=True
            )
            
            logger.info("Neo4j container started successfully")
            logger.debug(f"Docker compose output: {result.stdout}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start Neo4j container: {e}")
            logger.error(f"Error output: {e.stderr}")
            return False
    
    def wait_for_neo4j_ready(self, timeout: int = 120) -> bool:
        """
        Wait for Neo4j to be ready to accept connections.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if Neo4j is ready, False if timeout
        """
        logger.info("Waiting for Neo4j to be ready...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                driver = GraphDatabase.driver(
                    self.neo4j_uri,
                    auth=(self.neo4j_user, self.neo4j_password)
                )
                
                with driver.session() as session:
                    result = session.run("RETURN 1 as test")
                    if result.single()["test"] == 1:
                        driver.close()
                        logger.info("Neo4j is ready!")
                        return True
                        
            except ServiceUnavailable:
                logger.debug("Neo4j not ready yet, waiting...")
                time.sleep(2)
            except Exception as e:
                logger.debug(f"Connection attempt failed: {e}")
                time.sleep(2)
        
        logger.error(f"Neo4j did not become ready within {timeout} seconds")
        return False
    
    def stop_neo4j_container(self) -> bool:
        """Stop Neo4j container."""
        if not self.is_compose_available():
            logger.error("Docker Compose is not available")
            return False
        
        try:
            compose_cmd = self.get_compose_command()
            logger.info("Stopping Neo4j container...")
            
            result = subprocess.run(
                compose_cmd + ['-f', self.compose_file, 'stop', 'neo4j'],
                capture_output=True, text=True, check=True
            )
            
            logger.info("Neo4j container stopped successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to stop Neo4j container: {e}")
            return False
    
    def get_container_logs(self, lines: int = 50) -> Optional[str]:
        """Get recent logs from Neo4j container."""
        if not self.is_compose_available():
            return None
        
        try:
            compose_cmd = self.get_compose_command()
            result = subprocess.run(
                compose_cmd + ['-f', self.compose_file, 'logs', '--tail', str(lines), 'neo4j'],
                capture_output=True, text=True, check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get container logs: {e}")
            return None
    
    def setup_neo4j(self) -> bool:
        """
        Complete Neo4j setup: start container and wait for readiness.
        
        Returns:
            True if setup successful, False otherwise
        """
        logger.info("Setting up Neo4j container...")
        
        # Start the container
        if not self.start_neo4j_container():
            return False
        
        # Wait for it to be ready
        if not self.wait_for_neo4j_ready():
            logger.error("Neo4j setup failed - container did not become ready")
            logs = self.get_container_logs()
            if logs:
                logger.error(f"Container logs:\n{logs}")
            return False
        
        logger.info("Neo4j setup completed successfully!")
        return True
