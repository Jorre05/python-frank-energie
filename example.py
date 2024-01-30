"""Example of using python-frank-energie."""

import asyncio
import os
from datetime import datetime, timedelta

from python_frank_energie import FrankEnergie
from python_frank_energie.frank_energie import FrankCountry


async def main():
    """Fetch and print data from Frank energie."""
    today = datetime.utcnow().date()
    tomorrow = today + timedelta(days=1)
    day_after_tomorrow = today + timedelta(days=2)

    async with FrankEnergie(country=FrankCountry.Belgium) as fe:

        prices_today = await fe.prices(today, tomorrow)
        prices_tomorrow = await fe.prices(tomorrow, day_after_tomorrow)

        for price in (prices_today.electricity + prices_tomorrow.electricity).all:
            print(f"Electricity: {price.date_from} -> {price.date_till}: {price.total}")

        for price in (prices_today.gas + prices_tomorrow.gas).all:
            print(f"Gas: {price.date_from} -> {price.date_till}: {price.total}")

    async with FrankEnergie(country=FrankCountry.Belgium) as fe:
        authToken = await fe.login("pieter@vanoost.cloud", "YZthfV.q9g4B")

        user = await fe.user()

        user_prices_today = await fe.user_prices(today)
        user_prices_tomorrow = await fe.user_prices(tomorrow)

        for price in (
            user_prices_today.electricity + user_prices_tomorrow.electricity
        ).all:
            print(f"Electricity: {price.date_from} -> {price.date_till}: {price.total}")

        for price in (user_prices_today.gas + user_prices_tomorrow.gas).all:
            print(f"Gas: {price.date_from} -> {price.date_till}: {price.total}")

        print(await fe.month_summary())
        print(await fe.invoices())

    # async with FrankEnergie(auth_token=authToken.authToken) as fe:
    #     print(await fe.month_summary())
    #     print(await fe.user())


asyncio.run(main())
