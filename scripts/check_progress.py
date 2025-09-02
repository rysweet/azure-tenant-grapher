#!/usr/bin/env python3
"""
Quick script to check the progress of the Azure Tenant Grapher by querying Neo4j
"""

import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

# Load environment variables
load_dotenv()


def check_database_progress() -> None:
    """Check the current state of the Neo4j database."""

    # Connect to Neo4j
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD")
    if not neo4j_password:
        raise ValueError("NEO4J_PASSWORD environment variable is required")

    try:
        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

        with driver.session() as session:
            print("🔍 Checking Neo4j database progress...")
            print("=" * 50)

            # Check subscription nodes
            result = session.run("MATCH (s:Subscription) RETURN count(s) as count")
            sub_record = result.single()
            subscription_count = sub_record["count"] if sub_record else 0
            print(f"📊 Subscriptions: {subscription_count}")

            # Check resource nodes
            result = session.run("MATCH (r:Resource) RETURN count(r) as count")
            res_record = result.single()
            resource_count = res_record["count"] if res_record else 0
            print(f"📦 Resources: {resource_count}")

            # Check resource groups
            result = session.run("MATCH (rg:ResourceGroup) RETURN count(rg) as count")
            rg_record = result.single()
            rg_count = rg_record["count"] if rg_record else 0
            print(f"📁 Resource Groups: {rg_count}")

            # Check resources with LLM descriptions
            result = session.run(
                """
                MATCH (r:Resource)
                WHERE r.llm_description IS NOT NULL AND r.llm_description <> ''
                RETURN count(r) as count
            """
            )
            llm_record = result.single()
            llm_count = llm_record["count"] if llm_record else 0
            print(f"🤖 Resources with LLM descriptions: {llm_count}")

            # Check relationships
            result = session.run("MATCH ()-[rel]->() RETURN count(rel) as count")
            rel_record = result.single()
            rel_count = rel_record["count"] if rel_record else 0
            print(f"🔗 Relationships: {rel_count}")

            print("=" * 50)

            if resource_count > 0:
                progress_pct = (
                    (llm_count / resource_count) * 100 if resource_count > 0 else 0
                )
                print(
                    f"📈 LLM Progress: {progress_pct:.1f}% ({llm_count}/{resource_count})"
                )

                # Show some sample resources
                print("\n🔍 Sample resources in database:")
                result = session.run(
                    """
                    MATCH (r:Resource)
                    RETURN r.name, r.type, r.location,
                           CASE WHEN r.llm_description IS NOT NULL AND r.llm_description <> ''
                                THEN 'YES' ELSE 'NO' END as has_llm
                    LIMIT 5
                """
                )

                for record in result:
                    name = (
                        record["r.name"][:30] + "..."
                        if len(record["r.name"]) > 30
                        else record["r.name"]
                    )
                    resource_type = (
                        record["r.type"].split("/")[-1]
                        if "/" in record["r.type"]
                        else record["r.type"]
                    )
                    location = record["r.location"]
                    has_llm = record["has_llm"]
                    print(
                        f"   • {name} ({resource_type}) in {location} - LLM: {has_llm}"
                    )

                # Show recent resources with LLM descriptions
                if llm_count > 0:
                    print("\n🤖 Recent LLM-enhanced resources:")
                    result = session.run(
                        """
                        MATCH (r:Resource)
                        WHERE r.llm_description IS NOT NULL AND r.llm_description <> ''
                        RETURN r.name, r.type, r.llm_description
                        LIMIT 3
                    """
                    )

                    for record in result:
                        name = (
                            record["r.name"][:25] + "..."
                            if len(record["r.name"]) > 25
                            else record["r.name"]
                        )
                        resource_type = (
                            record["r.type"].split("/")[-1]
                            if "/" in record["r.type"]
                            else record["r.type"]
                        )
                        desc_preview = (
                            record["r.llm_description"][:100] + "..."
                            if len(record["r.llm_description"]) > 100
                            else record["r.llm_description"]
                        )
                        print(f"   • {name} ({resource_type})")
                        print(f'     └─ "{desc_preview}"')

            print("\n✅ Database query completed successfully!")

        driver.close()

    except Exception as e:
        print(f"❌ Error connecting to Neo4j: {e}")
        print("💡 Make sure Neo4j is running on bolt://localhost:7687")


def main() -> None:
    check_database_progress()


if __name__ == "__main__":
    main()
