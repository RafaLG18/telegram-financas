"""Order matters: `quick` is the text catch-all and must come last."""

from aiogram import Router

from . import quick, record, reports, start


def build_router() -> Router:
    root = Router(name="root")
    root.include_router(start.router)
    root.include_router(record.router)
    root.include_router(reports.router)
    root.include_router(quick.router)
    return root


__all__ = ["build_router"]
