from __future__ import annotations

from typing import Any

from app.clients.oceansx import OceansXClient


async def get_cargo_throughput(client: OceansXClient, months: int = 12) -> list[dict[str, Any]]:
    return await client.cargo_monthly_throughput(months)


async def get_container_throughput(client: OceansXClient, months: int = 12) -> list[dict[str, Any]]:
    return await client.container_monthly_throughput(months)


async def get_bunkers_sales(client: OceansXClient, months: int = 12) -> list[dict[str, Any]]:
    return await client.bunkers_monthly_sales(months)


async def get_shipping_tonnage(client: OceansXClient, months: int = 12) -> list[dict[str, Any]]:
    return await client.shipping_monthly_tonnage(months)


async def get_vessel_call_volume(client: OceansXClient, months: int = 12) -> list[dict[str, Any]]:
    return await client.monthly_vessel_call_volume(months)
