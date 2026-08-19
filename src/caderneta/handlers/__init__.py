"""Ordem importa: `rapido` e catch-all de texto e precisa vir por ultimo."""

from aiogram import Router

from . import rapido, registrar, relatorios, start


def montar_router() -> Router:
    raiz = Router(name="raiz")
    raiz.include_router(start.router)
    raiz.include_router(registrar.router)
    raiz.include_router(relatorios.router)
    raiz.include_router(rapido.router)
    return raiz


__all__ = ["montar_router"]
