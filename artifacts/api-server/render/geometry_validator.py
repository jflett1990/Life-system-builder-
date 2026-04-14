from __future__ import annotations

import asyncio
import os
import tempfile
from dataclasses import dataclass
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class GeometryProbeResult:
    status: str
    errors: list[str]
    warnings: list[str]
    stats: dict[str, int]
    diagnostics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "errors": self.errors,
            "warnings": self.warnings,
            "stats": self.stats,
            "diagnostics": self.diagnostics,
        }


async def _probe_with_playwright(html: str, timeout_ms: int = 20000) -> GeometryProbeResult:
    from playwright.async_api import async_playwright

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(html)
            tmp_path = f.name

        file_url = f"file://{tmp_path}"

        import shutil

        system_chromium = shutil.which("chromium") or shutil.which("chromium-browser")

        async with async_playwright() as pw:
            kwargs: dict[str, Any] = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
            if system_chromium:
                kwargs["executable_path"] = system_chromium

            browser = await pw.chromium.launch(**kwargs)
            page = await browser.new_page()
            await page.goto(file_url, wait_until="domcontentloaded", timeout=timeout_ms)
            await page.wait_for_function("window.__lsb_pdf_ready === true", timeout=timeout_ms)

            diagnostics = await page.evaluate(
                """
                () => {
                  const paged = window.__lsb_render_diagnostics || {};
                  const pageNodes = Array.from(document.querySelectorAll('.pagedjs_page'));

                  let overflow_blocks = 0;
                  const clipped = [];
                  for (const node of pageNodes) {
                    const content = node.querySelector('.pagedjs_page_content, .pagedjs_area, .pagedjs_pagebox');
                    if (!content) continue;
                    if ((content.scrollHeight - content.clientHeight) > 1) {
                      overflow_blocks += 1;
                      clipped.push({
                        page: pageNodes.indexOf(node) + 1,
                        overflow_px: Math.round(content.scrollHeight - content.clientHeight),
                      });
                    }
                  }

                  const splitWorksheetHeaders = [];
                  for (const header of document.querySelectorAll('.worksheet-section__header')) {
                    const next = header.nextElementSibling;
                    if (!next) continue;
                    const hp = header.closest('.pagedjs_page');
                    const np = next.closest('.pagedjs_page');
                    if (hp && np && hp !== np) {
                      splitWorksheetHeaders.push((header.textContent || '').trim().slice(0, 120));
                    }
                  }

                  return {
                    page_count: pageNodes.length,
                    overflow_blocks,
                    clipped,
                    splitWorksheetHeaders,
                    orphaned_headers: (paged.orphaned_headers || []).length,
                    split_structures: (paged.split_structures || []).length,
                    underfilled_pages: (paged.underfilled_pages || []).length,
                    raw: paged,
                  }
                }
                """
            )
            await browser.close()

        errors: list[str] = []
        warnings: list[str] = []

        if diagnostics.get("overflow_blocks", 0) > 0:
            errors.append(f"Detected {diagnostics['overflow_blocks']} overflow blocks after pagination")
        if diagnostics.get("splitWorksheetHeaders"):
            errors.append(f"Detected {len(diagnostics['splitWorksheetHeaders'])} worksheet headers split from body")
        if diagnostics.get("orphaned_headers", 0) > 0:
            errors.append(f"Detected {diagnostics['orphaned_headers']} orphaned headings")
        if diagnostics.get("split_structures", 0) > 0:
            errors.append(f"Detected {diagnostics['split_structures']} split structural blocks")
        if diagnostics.get("underfilled_pages", 0) > 2:
            warnings.append(f"Detected {diagnostics['underfilled_pages']} underfilled pages")

        return GeometryProbeResult(
            status="pass" if not errors else "fail",
            errors=errors,
            warnings=warnings,
            stats={
                "page_count": int(diagnostics.get("page_count", 0)),
                "overflow_blocks": int(diagnostics.get("overflow_blocks", 0)),
                "split_worksheet_headers": len(diagnostics.get("splitWorksheetHeaders", [])),
                "orphaned_headers": int(diagnostics.get("orphaned_headers", 0)),
                "split_structures": int(diagnostics.get("split_structures", 0)),
            },
            diagnostics=diagnostics,
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def probe_layout(html: str, timeout_ms: int = 20000) -> GeometryProbeResult:
    try:
        return asyncio.run(_probe_with_playwright(html, timeout_ms=timeout_ms))
    except Exception as exc:
        logger.warning("Layout geometry probe unavailable: %s", exc)
        return GeometryProbeResult(
            status="warning",
            errors=[],
            warnings=[f"Layout geometry probe unavailable: {exc}"],
            stats={
                "page_count": 0,
                "overflow_blocks": 0,
                "split_worksheet_headers": 0,
                "orphaned_headers": 0,
                "split_structures": 0,
            },
            diagnostics={"error": str(exc)},
        )
