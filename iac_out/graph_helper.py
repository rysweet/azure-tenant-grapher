#!/usr/bin/env python3
"""
Graph Helper script for AAD objects creation and deletion via Microsoft Graph SDK.
"""

import json
import os
import sys

try:
    import yaml
except ImportError:
    yaml = None

from azure.identity import ClientSecretCredential

try:
    from msgraph.core import GraphClient
except ImportError:
    try:
        from msgraph_core.graph_client import GraphClient
    except ImportError:
        GraphClient = None


def load_data(file_path):
    with open(file_path) as f:
        if file_path.endswith((".yaml", ".yml")):
            if yaml:
                return yaml.safe_load(f)
            else:
                raise ImportError("PyYAML is required to load YAML files.")
        return json.load(f)


def get_graph_client():
    if GraphClient is None:
        print(
            "Error: Microsoft Graph SDK is not installed or importable as msgraph.core or msgraph_core.graph_client.",
            file=sys.stderr,
        )
        sys.exit(1)
    tenant_id = os.getenv("TENANT_ID")
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    if not all([tenant_id, client_id, client_secret]):
        print(
            "Error: TENANT_ID, CLIENT_ID, and CLIENT_SECRET environment variables must be set.",
            file=sys.stderr,
        )
        sys.exit(1)
    cred = ClientSecretCredential(
        tenant_id=tenant_id, client_id=client_id, client_secret=client_secret
    )
    client = GraphClient(credential=cred)
    return client


def confirm_action(action, count):
    resp = input(f"Are you sure you want to {action} {count} objects? [y/N]: ")
    return resp.strip().lower() in ("y", "yes")


def create_aad_objects(data_file_path):
    data = load_data(data_file_path)
    users = data.get("users", [])
    groups = data.get("groups", [])
    sps = data.get("service_principals", [])
    total = len(users) + len(groups) + len(sps)
    if total == 0:
        print("No AAD objects to create.")
        return
    if not confirm_action("create", total):
        print("Operation canceled.")
        return
    client = get_graph_client()
    # Create users
    for obj in users:
        obj_id = obj.get("id")
        if obj_id:
            resp = client.get(f"/users/{obj_id}")
            if resp.status_code == 200:
                print(f"User {obj_id} exists, skipping creation.")
                continue
        resp = client.post("/users", json=obj)
        if resp.status_code in (200, 201):
            created = resp.json().get("id")
            print(f"Created user {created}.")
        else:
            print(f"Failed to create user: {resp.status_code} - {resp.text}")
    # Create groups
    for obj in groups:
        obj_id = obj.get("id")
        if obj_id:
            resp = client.get(f"/groups/{obj_id}")
            if resp.status_code == 200:
                print(f"Group {obj_id} exists, skipping creation.")
                continue
        resp = client.post("/groups", json=obj)
        if resp.status_code in (200, 201):
            created = resp.json().get("id")
            print(f"Created group {created}.")
        else:
            print(f"Failed to create group: {resp.status_code} - {resp.text}")
    # Create service principals
    for obj in sps:
        obj_id = obj.get("id")
        if obj_id:
            resp = client.get(f"/servicePrincipals/{obj_id}")
            if resp.status_code == 200:
                print(f"Service principal {obj_id} exists, skipping creation.")
                continue
        resp = client.post("/servicePrincipals", json=obj)
        if resp.status_code in (200, 201):
            created = resp.json().get("id")
            print(f"Created service principal {created}.")
        else:
            print(
                f"Failed to create service principal: {resp.status_code} - {resp.text}"
            )


def delete_aad_objects(data_file_path):
    data = load_data(data_file_path)
    users = data.get("users", [])
    groups = data.get("groups", [])
    sps = data.get("service_principals", [])
    total = len(users) + len(groups) + len(sps)
    if total == 0:
        print("No AAD objects to delete.")
        return
    if not confirm_action("delete", total):
        print("Operation canceled.")
        return
    client = get_graph_client()
    # Delete users
    for obj in users:
        obj_id = obj.get("id")
        if not obj_id:
            continue
        resp = client.delete(f"/users/{obj_id}")
        if resp.status_code in (200, 204):
            print(f"Deleted user {obj_id}.")
        else:
            print(f"Failed to delete user {obj_id}: {resp.status_code} - {resp.text}")
    # Delete groups
    for obj in groups:
        obj_id = obj.get("id")
        if not obj_id:
            continue
        resp = client.delete(f"/groups/{obj_id}")
        if resp.status_code in (200, 204):
            print(f"Deleted group {obj_id}.")
        else:
            print(f"Failed to delete group {obj_id}: {resp.status_code} - {resp.text}")
    # Delete service principals
    for obj in sps:
        obj_id = obj.get("id")
        if not obj_id:
            continue
        resp = client.delete(f"/servicePrincipals/{obj_id}")
        if resp.status_code in (200, 204):
            print(f"Deleted service principal {obj_id}.")
        else:
            print(
                f"Failed to delete service principal {obj_id}: {resp.status_code} - {resp.text}"
            )


def main():
    if len(sys.argv) < 3:
        print(
            "Usage: python graph_helper.py [create|delete] <aad_objects.json|.yaml>",
            file=sys.stderr,
        )
        sys.exit(1)
    action = sys.argv[1].lower()
    file_path = sys.argv[2]
    if action == "create":
        create_aad_objects(file_path)
    elif action in ("delete", "destroy"):
        delete_aad_objects(file_path)
    else:
        print(f"Unknown action '{action}'. Use 'create' or 'delete'.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
