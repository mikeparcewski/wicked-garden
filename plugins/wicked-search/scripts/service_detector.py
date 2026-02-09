#!/usr/bin/env python3
"""
Service Detector for wicked-search.

Infers service architecture from infrastructure files and code patterns.
Uses a layered approach:
1. Parse infrastructure files (docker-compose, k8s, terraform) - preferred
2. Fall back to code analysis (JDBC strings, HTTP clients, etc.)

Features:
- Docker Compose parsing
- Kubernetes manifest parsing
- Code pattern detection (JDBC, HTTP clients, message queues)
- Merge strategy (infra + code, flag discrepancies)
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import yaml

from ignore_handler import get_ignore_handler


@dataclass
class ServiceNode:
    """Represents a service in the architecture."""
    id: str
    name: str
    type: str  # service, database, api, queue, external
    technology: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    inferred_from: List[str] = field(default_factory=list)  # Sources of inference

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "technology": self.technology,
            "metadata": self.metadata,
            "inferred_from": self.inferred_from,
        }


@dataclass
class ServiceConnection:
    """Represents a connection between services."""
    source_id: str
    target_id: str
    connection_type: str  # http, jdbc, amqp, grpc, redis, etc.
    protocol: Optional[str] = None
    evidence: List[str] = field(default_factory=list)
    confidence: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "connection_type": self.connection_type,
            "protocol": self.protocol,
            "evidence": self.evidence,
            "confidence": self.confidence,
        }


class ServiceDetector:
    """Detects services from infrastructure and code."""

    def __init__(self, project_root: Path, db_path: Optional[Path] = None):
        """
        Initialize service detector.

        Args:
            project_root: Root directory of the project
            db_path: Optional path to symbol graph database
        """
        self.project_root = project_root
        self.db_path = db_path
        self.services: Dict[str, ServiceNode] = {}
        self.connections: List[ServiceConnection] = []

    def detect_all(self) -> Dict[str, Any]:
        """
        Detect all services using layered approach.

        Returns:
            Dict with services, connections, and metadata
        """
        # Layer 1: Infrastructure files (preferred)
        self._detect_from_docker_compose()
        self._detect_from_kubernetes()

        # Layer 2: Code patterns (fallback)
        self._detect_from_code_patterns()

        return {
            "services": [s.to_dict() for s in self.services.values()],
            "connections": [c.to_dict() for c in self.connections],
            "metadata": {
                "total_services": len(self.services),
                "total_connections": len(self.connections),
                "sources": self._get_sources(),
            }
        }

    def _get_sources(self) -> List[str]:
        """Get list of sources used for detection."""
        sources = set()
        for service in self.services.values():
            sources.update(service.inferred_from)
        return sorted(sources)

    def _detect_from_docker_compose(self) -> None:
        """Parse docker-compose files for services."""
        compose_files = list(self.project_root.glob("**/docker-compose*.yml")) + \
                        list(self.project_root.glob("**/docker-compose*.yaml"))

        for compose_file in compose_files:
            try:
                with open(compose_file, 'r') as f:
                    compose = yaml.safe_load(f)

                if not compose or 'services' not in compose:
                    continue

                source = f"docker-compose:{compose_file.relative_to(self.project_root)}"

                for service_name, service_config in compose.get('services', {}).items():
                    service_id = f"service:{service_name}"

                    # Determine service type and technology
                    image = service_config.get('image', '')
                    service_type = self._infer_service_type_from_image(image)
                    technology = self._extract_technology(image)

                    service = ServiceNode(
                        id=service_id,
                        name=service_name,
                        type=service_type,
                        technology=technology,
                        metadata={
                            "image": image,
                            "ports": service_config.get('ports', []),
                            "environment": list(service_config.get('environment', {}).keys()) if isinstance(service_config.get('environment'), dict) else [],
                        },
                        inferred_from=[source]
                    )
                    self._add_service(service)

                    # Detect connections from depends_on
                    for dep in service_config.get('depends_on', []):
                        if isinstance(dep, str):
                            dep_name = dep
                        elif isinstance(dep, dict):
                            dep_name = list(dep.keys())[0] if dep else None
                        else:
                            continue

                        if dep_name:
                            conn = ServiceConnection(
                                source_id=service_id,
                                target_id=f"service:{dep_name}",
                                connection_type="depends_on",
                                confidence="high",
                                evidence=[source]
                            )
                            self.connections.append(conn)

                    # Detect connections from links
                    for link in service_config.get('links', []):
                        link_name = link.split(':')[0] if ':' in link else link
                        conn = ServiceConnection(
                            source_id=service_id,
                            target_id=f"service:{link_name}",
                            connection_type="link",
                            confidence="high",
                            evidence=[source]
                        )
                        self.connections.append(conn)

            except Exception as e:
                print(f"Error parsing {compose_file}: {e}")

    def _detect_from_kubernetes(self) -> None:
        """Parse Kubernetes manifests for services."""
        k8s_files = list(self.project_root.glob("**/k8s/**/*.yaml")) + \
                    list(self.project_root.glob("**/k8s/**/*.yml")) + \
                    list(self.project_root.glob("**/kubernetes/**/*.yaml")) + \
                    list(self.project_root.glob("**/kubernetes/**/*.yml"))

        for k8s_file in k8s_files:
            try:
                with open(k8s_file, 'r') as f:
                    # Handle multi-document YAML
                    docs = list(yaml.safe_load_all(f))

                source = f"kubernetes:{k8s_file.relative_to(self.project_root)}"

                for doc in docs:
                    if not doc or 'kind' not in doc:
                        continue

                    kind = doc.get('kind')
                    metadata = doc.get('metadata', {})
                    name = metadata.get('name', 'unknown')

                    if kind in ('Deployment', 'StatefulSet', 'DaemonSet'):
                        service_id = f"k8s:{kind.lower()}:{name}"

                        # Extract container info
                        spec = doc.get('spec', {}).get('template', {}).get('spec', {})
                        containers = spec.get('containers', [])
                        image = containers[0].get('image', '') if containers else ''

                        service = ServiceNode(
                            id=service_id,
                            name=name,
                            type=self._infer_service_type_from_image(image),
                            technology=self._extract_technology(image),
                            metadata={
                                "kind": kind,
                                "image": image,
                                "replicas": doc.get('spec', {}).get('replicas'),
                            },
                            inferred_from=[source]
                        )
                        self._add_service(service)

                    elif kind == 'Service':
                        # K8s Service exposes a deployment
                        service_id = f"k8s:service:{name}"
                        service = ServiceNode(
                            id=service_id,
                            name=name,
                            type="service",
                            metadata={
                                "kind": kind,
                                "type": doc.get('spec', {}).get('type', 'ClusterIP'),
                                "ports": doc.get('spec', {}).get('ports', []),
                            },
                            inferred_from=[source]
                        )
                        self._add_service(service)

            except Exception as e:
                print(f"Error parsing {k8s_file}: {e}")

    def _detect_from_code_patterns(self) -> None:
        """Detect services from code patterns."""
        if not self.db_path or not self.db_path.exists():
            # Fall back to file scanning
            self._scan_files_for_patterns()
            return

        # Use symbol graph if available
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Look for connection patterns in metadata
        cursor.execute("""
            SELECT id, name, type, metadata, file_path
            FROM symbols
            WHERE metadata LIKE '%jdbc%'
               OR metadata LIKE '%http%'
               OR metadata LIKE '%amqp%'
               OR metadata LIKE '%redis%'
               OR metadata LIKE '%kafka%'
               OR metadata LIKE '%mongo%'
        """)

        for row in cursor.fetchall():
            metadata = json.loads(row['metadata']) if row['metadata'] else {}
            self._process_code_pattern(row['file_path'], metadata)

        conn.close()

    def _discover_scannable_files(self, ignore_handler) -> List[Path]:
        """Dynamically discover scannable files, prioritizing config files."""
        # Config file extensions (most likely to have connection strings)
        config_extensions = {
            '.properties', '.yml', '.yaml', '.xml', '.json',
            '.env', '.conf', '.ini', '.toml', '.cfg'
        }

        # Source file extensions
        source_extensions = {
            '.java', '.py', '.ts', '.js', '.go', '.rs', '.rb',
            '.php', '.cs', '.kt', '.scala', '.groovy', '.clj'
        }

        # First, sample the project to see what file types exist
        sample_files = list(self.project_root.glob("**/*"))[:5000]
        found_extensions: Set[str] = set()
        for f in sample_files:
            if f.is_file() and not ignore_handler.is_ignored(str(f)):
                found_extensions.add(f.suffix.lower())

        # Determine which extensions to scan
        config_to_scan = config_extensions & found_extensions
        source_to_scan = source_extensions & found_extensions

        # Collect files: config first, then source
        config_files: List[Path] = []
        source_files: List[Path] = []

        for ext in config_to_scan:
            config_files.extend(self.project_root.glob(f"**/*{ext}"))

        for ext in source_to_scan:
            source_files.extend(self.project_root.glob(f"**/*{ext}"))

        # Filter and prioritize
        all_files = config_files + source_files
        all_files = [f for f in all_files if not ignore_handler.is_ignored(str(f))]

        return all_files

    def _scan_files_for_patterns(self) -> None:
        """Scan source files for connection patterns."""
        patterns = {
            # Standard JDBC format: jdbc:driver://host:port/db
            'jdbc': (r'jdbc:(\w+)://([^/\s"\']+)', 'database'),
            # Oracle JDBC format: jdbc:oracle:thin:@host:port:sid
            'jdbc_oracle': (r'jdbc:oracle:\w+:@([^:\s"\']+):(\d+):(\w+)', 'database'),
            'http_client': (r'https?://([^/\s"\'<>]+)', 'external'),
            'amqp': (r'amqp://([^/\s"\']+)', 'queue'),
            'redis': (r'redis://([^/\s"\']+)', 'cache'),
            'mongodb': (r'mongodb://([^/\s"\']+)', 'database'),
        }

        # Use ignore handler to filter out .venv, node_modules, etc.
        ignore_handler = get_ignore_handler(str(self.project_root))

        # Dynamically discover file types in the project
        all_files = self._discover_scannable_files(ignore_handler)

        for source_file in all_files[:2000]:  # Limit for performance
            try:
                content = source_file.read_text(errors='ignore')

                for pattern_name, (regex, service_type) in patterns.items():
                    matches = re.findall(regex, content, re.IGNORECASE)
                    for match in matches:
                        # Handle different match formats
                        if pattern_name == 'jdbc_oracle':
                            # Oracle: (host, port, sid)
                            host = f"{match[0]}:{match[1]}:{match[2]}"
                            technology = "oracle"
                        elif pattern_name == 'jdbc':
                            # Standard JDBC: (driver, host)
                            host = match[1] if isinstance(match, tuple) else match
                            technology = match[0] if isinstance(match, tuple) else "jdbc"
                        else:
                            host = match[1] if isinstance(match, tuple) and len(match) > 1 else match
                            if isinstance(match, tuple):
                                host = match[0]
                            technology = pattern_name

                        # Skip localhost and common test hosts
                        if any(skip in str(host).lower() for skip in ('localhost', '127.0.0.1', 'example.com', 'example.org')):
                            continue

                        # Clean up the host (remove trailing punctuation)
                        host = str(host).rstrip('.,;:\'\")')

                        service_id = f"inferred:{pattern_name}:{host}"
                        service = ServiceNode(
                            id=service_id,
                            name=host,
                            type=service_type,
                            technology=technology,
                            metadata={"pattern": pattern_name},
                            inferred_from=[f"code:{source_file.relative_to(self.project_root)}"]
                        )
                        self._add_service(service)

            except Exception:
                continue

    def _process_code_pattern(self, file_path: str, metadata: Dict) -> None:
        """Process a code pattern found in metadata."""
        # Implementation for processing patterns from symbol metadata
        pass

    def _add_service(self, service: ServiceNode) -> None:
        """Add or merge a service."""
        if service.id in self.services:
            # Merge: combine inferred_from sources
            existing = self.services[service.id]
            existing.inferred_from.extend(service.inferred_from)
            existing.inferred_from = list(set(existing.inferred_from))
        else:
            self.services[service.id] = service

    def _infer_service_type_from_image(self, image: str) -> str:
        """Infer service type from Docker image name."""
        image_lower = image.lower()

        if any(db in image_lower for db in ['postgres', 'mysql', 'mariadb', 'oracle', 'mssql', 'mongo', 'cockroach']):
            return 'database'
        elif any(cache in image_lower for cache in ['redis', 'memcached', 'hazelcast']):
            return 'cache'
        elif any(queue in image_lower for queue in ['rabbitmq', 'kafka', 'activemq', 'nats']):
            return 'queue'
        elif any(proxy in image_lower for proxy in ['nginx', 'traefik', 'haproxy', 'envoy']):
            return 'proxy'
        elif any(search in image_lower for search in ['elasticsearch', 'solr', 'opensearch']):
            return 'search'
        else:
            return 'service'

    def _extract_technology(self, image: str) -> Optional[str]:
        """Extract technology name from image."""
        if not image:
            return None

        # Remove registry prefix
        parts = image.split('/')
        image_name = parts[-1]

        # Remove tag
        if ':' in image_name:
            image_name = image_name.split(':')[0]

        return image_name

    def save_to_database(self, db_path: Path) -> int:
        """
        Save detected services and connections to database.

        Args:
            db_path: Path to SQLite database

        Returns:
            Number of services saved
        """
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        saved = 0
        for service in self.services.values():
            try:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO service_nodes
                    (id, name, type, technology, metadata, inferred_from, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                    """,
                    (
                        service.id,
                        service.name,
                        service.type,
                        service.technology,
                        json.dumps(service.metadata),
                        json.dumps(service.inferred_from),
                    )
                )
                saved += 1
            except Exception as e:
                print(f"Error saving service {service.id}: {e}")

        for conn_obj in self.connections:
            try:
                cursor.execute(
                    """
                    INSERT INTO service_connections
                    (source_service_id, target_service_id, connection_type, protocol, evidence, confidence, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                    """,
                    (
                        conn_obj.source_id,
                        conn_obj.target_id,
                        conn_obj.connection_type,
                        conn_obj.protocol,
                        json.dumps(conn_obj.evidence),
                        conn_obj.confidence,
                    )
                )
            except Exception as e:
                print(f"Error saving connection: {e}")

        conn.commit()
        conn.close()
        return saved


def format_mermaid(services: List[ServiceNode], connections: List[ServiceConnection]) -> str:
    """Format service map as Mermaid diagram."""
    lines = ["graph TD"]

    # Style definitions
    lines.append("  classDef database fill:#f9f,stroke:#333")
    lines.append("  classDef queue fill:#bbf,stroke:#333")
    lines.append("  classDef cache fill:#bfb,stroke:#333")
    lines.append("  classDef external fill:#fbb,stroke:#333")

    # Add nodes
    for service in services:
        node_id = service.id.replace(":", "_").replace(".", "_")
        label = f"{service.name}"
        if service.technology:
            label += f"<br/>{service.technology}"

        shape_start, shape_end = "[", "]"
        if service.type == "database":
            shape_start, shape_end = "[(", ")]"
        elif service.type == "queue":
            shape_start, shape_end = "[[", "]]"
        elif service.type == "external":
            shape_start, shape_end = "((", "))"

        lines.append(f"  {node_id}{shape_start}\"{label}\"{shape_end}")

        # Add class
        if service.type in ("database", "queue", "cache", "external"):
            lines.append(f"  class {node_id} {service.type}")

    # Add edges
    seen_edges = set()
    for conn in connections:
        source_id = conn.source_id.replace(":", "_").replace(".", "_")
        target_id = conn.target_id.replace(":", "_").replace(".", "_")
        edge_key = f"{source_id}->{target_id}"

        if edge_key not in seen_edges:
            label = conn.connection_type if conn.connection_type != "depends_on" else ""
            if label:
                lines.append(f"  {source_id} -->|{label}| {target_id}")
            else:
                lines.append(f"  {source_id} --> {target_id}")
            seen_edges.add(edge_key)

    return "\n".join(lines)


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Detect service architecture")
    parser.add_argument("project_root", nargs="?", default=".", help="Project root directory")
    parser.add_argument("--db", help="Path to symbol graph database")
    parser.add_argument("--format", choices=["json", "mermaid", "table"], default="table",
                        help="Output format")
    parser.add_argument("--save", help="Save to database at path")

    args = parser.parse_args()

    project_root = Path(args.project_root)
    db_path = Path(args.db) if args.db else None

    detector = ServiceDetector(project_root, db_path)
    result = detector.detect_all()

    if args.save:
        saved = detector.save_to_database(Path(args.save))
        print(f"Saved {saved} services to {args.save}")

    if args.format == "json":
        print(json.dumps(result, indent=2))
    elif args.format == "mermaid":
        print(format_mermaid(list(detector.services.values()), detector.connections))
    else:
        # Table format
        print(f"\n## Service Map\n")
        print(f"Total Services: {len(detector.services)}")
        print(f"Total Connections: {len(detector.connections)}")
        print(f"Sources: {', '.join(result['metadata']['sources'])}")

        print("\n### Services\n")
        print("| Name | Type | Technology | Source |")
        print("|------|------|------------|--------|")
        for service in detector.services.values():
            sources = ", ".join(service.inferred_from[:2])
            print(f"| {service.name} | {service.type} | {service.technology or '-'} | {sources} |")

        if detector.connections:
            print("\n### Connections\n")
            print("| Source | Target | Type |")
            print("|--------|--------|------|")
            for conn in detector.connections[:20]:
                print(f"| {conn.source_id} | {conn.target_id} | {conn.connection_type} |")


if __name__ == "__main__":
    main()
