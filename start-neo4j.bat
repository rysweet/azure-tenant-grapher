@echo off
REM Batch script to start Neo4j container only

echo Starting Neo4j container...
C:\Users\rysweet\src\td\.venv\Scripts\python.exe azure_tenant_grapher.py --tenant-id dummy --container-only

echo.
echo Neo4j container started successfully!
echo You can access Neo4j Browser at: http://localhost:7474
echo Username: neo4j
echo Password: azure-grapher-2024
echo.
echo The container will continue running in the background.
echo To stop it, run: docker-compose down

pause
