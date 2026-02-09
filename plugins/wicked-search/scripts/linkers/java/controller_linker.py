"""
Controller-to-View Linker.

Links controller methods to the JSP/HTML views they return.
Based on Ohio team's implementation.
"""

import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from symbol_graph import (
    SymbolGraph,
    Symbol,
    Reference,
    SymbolType,
    ReferenceType,
    Confidence,
)
from linkers.base import BaseLinker, register_linker

logger = logging.getLogger(__name__)


@register_linker
class ControllerLinker(BaseLinker):
    """Links controllers to their views."""

    # Linker metadata
    name = "controller"
    description = "Links Spring controllers to JSP/HTML views"
    priority = 30  # Run after EL resolver

    def __init__(self, graph: SymbolGraph):
        """
        Initialize linker.

        Args:
            graph: Symbol graph to work with
        """
        super().__init__(graph)

    def link_all(self) -> int:
        """
        Link all controllers to their views.

        Returns:
            Number of links created
        """
        links_created = 0

        # Link controller methods that have view metadata
        controller_methods = self.graph.find_by_type(SymbolType.CONTROLLER_METHOD)
        for method in controller_methods:
            refs = self.link_method(method)
            for ref in refs:
                self.graph.add_reference(ref)
            links_created += len(refs)

        # Also check controllers directly
        controllers = self.graph.find_by_type(SymbolType.CONTROLLER)
        for controller in controllers:
            refs = self._link_controller_views(controller)
            for ref in refs:
                self.graph.add_reference(ref)
            links_created += len(refs)

        logger.info(f"Created {links_created} controller-view links")
        return links_created

    def link_method(self, method: Symbol) -> List[Reference]:
        """
        Link a controller method to its views.

        Args:
            method: Controller method symbol

        Returns:
            List of references created
        """
        references = []

        view_name = method.metadata.get("view")
        if not view_name:
            return references

        # Find matching JSP/HTML pages
        pages = self._find_pages_for_view(view_name)

        for page in pages:
            references.append(Reference(
                source_id=method.id,
                target_id=page.id,
                ref_type=ReferenceType.RETURNS_VIEW,
                confidence=Confidence.HIGH,
                evidence={
                    "view_name": view_name,
                    "page_path": page.file_path,
                },
            ))

            # Also create HANDLES reference for the URL mapping
            mapping = method.metadata.get("mapping")
            if mapping:
                references.append(Reference(
                    source_id=method.id,
                    target_id=page.id,
                    ref_type=ReferenceType.HANDLES,
                    confidence=Confidence.HIGH,
                    evidence={
                        "url_mapping": mapping,
                        "http_method": method.metadata.get("http_method", "GET"),
                    },
                ))

        return references

    def _link_controller_views(self, controller: Symbol) -> List[Reference]:
        """
        Link controller to views based on naming conventions.

        Args:
            controller: Controller symbol

        Returns:
            List of references created
        """
        references = []

        # Try to find views by controller name convention
        # PersonController -> person/*.jsp
        name = controller.name
        if name.endswith("Controller"):
            base_name = name[:-len("Controller")].lower()

            # Find matching JSP pages
            all_pages = (
                self.graph.find_by_type(SymbolType.JSP_PAGE) +
                self.graph.find_by_type(SymbolType.HTML_PAGE)
            )

            for page in all_pages:
                if base_name in page.file_path.lower():
                    references.append(Reference(
                        source_id=controller.id,
                        target_id=page.id,
                        ref_type=ReferenceType.RETURNS_VIEW,
                        confidence=Confidence.LOW,
                        evidence={"match": "naming_convention", "base_name": base_name},
                    ))

        return references

    def _find_pages_for_view(self, view_name: str) -> List[Symbol]:
        """
        Find JSP/HTML pages matching a view name.

        Handles various patterns:
        - "person/list" -> "WEB-INF/jsp/person/list.jsp"
        - "personList" -> "**/personList.jsp"

        Args:
            view_name: View name from controller

        Returns:
            List of matching page symbols
        """
        pages = []

        # Common prefixes in Spring MVC
        prefixes = [
            "WEB-INF/jsp/",
            "WEB-INF/views/",
            "templates/",
            "webapp/",
            "",
        ]

        # Extensions to try
        extensions = [".jsp", ".html", ".jspx", ".xhtml", ""]

        # Generate possible paths
        possible_paths = []
        for prefix in prefixes:
            for ext in extensions:
                possible_paths.append(f"{prefix}{view_name}{ext}")
                if not view_name.endswith(ext) and ext:
                    possible_paths.append(f"{prefix}{view_name}")

        # Search all pages
        all_pages = (
            self.graph.find_by_type(SymbolType.JSP_PAGE) +
            self.graph.find_by_type(SymbolType.JSP_INCLUDE) +
            self.graph.find_by_type(SymbolType.HTML_PAGE)
        )

        for page in all_pages:
            page_path = page.file_path

            for possible in possible_paths:
                if page_path.endswith(possible) or possible in page_path:
                    if page not in pages:
                        pages.append(page)
                    break

        return pages
