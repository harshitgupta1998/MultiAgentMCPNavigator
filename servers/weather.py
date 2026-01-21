from mcp.server.fastmcp import FastMCP 
import httpx

mcp = FastMCP("Weather Server")

async def _geocode(query: str):
    async with httpx.AsyncClient(timeout=10) as c:
        # Attempt 1: exact query
        r = await c.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": query, "count": 1},
        )
        r.raise_for_status()
        data = r.json()
        if data.get("results"):
            x = data["results"][0]
            return x["latitude"], x["longitude"], x["name"], x.get("country_code")

        # Attempt 2: retry without commas / country
        simplified = query.split(",")[0].strip()
        r = await c.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": simplified, "count": 1},
        )
        r.raise_for_status()
        data = r.json()
        if data.get("results"):
            x = data["results"][0]
            return x["latitude"], x["longitude"], x["name"], x.get("country_code")

        return None

@mcp.tool()
async def get_weather(location: dict) -> str:
    """
    Get current weather.
    location = { city: str, state: str | None, country: str | None }
    """
    city = location.get("city")
    state = location.get("state")
    country = location.get("country")

    if not city:
        return "Missing city in location."

    # Build geocoding query string
    name = ", ".join([x for x in [city, state, country] if x])

    # 🔴 MISSING LINE — THIS WAS THE BUG
    g = await _geocode(name)
    if not g:
        return f"Couldn’t find '{name}'."

    lat, lon, resolved_name, resolved_country = g

    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current_weather": True,
            },
        )
        r.raise_for_status()
        cur = r.json().get("current_weather") or {}

    if not cur:
        return f"No weather data for {resolved_name}."

    return (
        f"{resolved_name}, {resolved_country}: "
        f"{cur.get('temperature')}°C, "
        f"wind {cur.get('windspeed')} km/h."
    )

if __name__ == "__main__":
    # serves MCP at http://localhost:8000/mcp
    mcp.run(transport="streamable-http")
