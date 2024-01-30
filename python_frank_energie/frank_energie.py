"""FrankEnergie API implementation."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from aiohttp.client import ClientError, ClientSession

from .exceptions import AuthException, AuthRequiredException
from .models import (
    Authentication,
    Invoices,
    MarketPrices,
    MonthSummary,
    User,
    FrankCountry,
)


class FrankEnergie:
    """FrankEnergie API."""

    DATA_URL = "https://frank-graphql-prod.graphcdn.app/"

    def __init__(
        self,
        clientsession: ClientSession = None,
        auth_token: str | None = None,
        refresh_token: str | None = None,
        country: FrankCountry | None = FrankCountry.Netherlands,
    ):
        """Initialize the FrankEnergie client."""
        self._country = country
        self._close_session: bool = False
        self._auth: Authentication | None = None
        self._session = clientsession
        self._siteReference = None

        if auth_token is not None or refresh_token is not None:
            self._auth = Authentication(auth_token, refresh_token)

    async def _query(self, query):
        if self._session is None:
            self._session = ClientSession()
            self._close_session = True

        try:
            resp = await self._session.post(
                self.DATA_URL,
                json=query,
                headers={
                    "Authorization": f"Bearer {self._auth.authToken}",
                    "X-Country": self._country.value,
                }
                if self._auth is not None
                else {"X-Country": self._country.value},
            )

            response = await resp.json()

        except (asyncio.TimeoutError, ClientError, KeyError) as error:
            raise ValueError(f"Request failed: {error}") from error

        # Catch common error messages and raise a more specific exception
        if errors := response.get("errors"):
            for error in errors:
                if error["message"] == "user-error:auth-not-authorised":
                    raise AuthException

        return response

    async def login(self, username: str, password: str) -> Authentication:
        """Login and get the authentication token."""
        query = {
            "query": """
                mutation Login($email: String!, $password: String!) {
                    login(email: $email, password: $password) {
                        authToken
                        refreshToken
                    }
                }
            """,
            "operationName": "Login",
            "variables": {"email": username, "password": password},
        }

        self._auth = Authentication.from_dict(await self._query(query))

        await self._load_site_reference()

        return self._auth

    async def renew_token(self) -> Authentication:
        """Renew the authentication token."""
        if self._auth is None:
            raise AuthRequiredException

        query = {
            "query": """
                mutation RenewToken($authToken: String!, $refreshToken: String!) {
                    renewToken(authToken: $authToken, refreshToken: $refreshToken) {
                        authToken
                        refreshToken
                    }
                }
            """,
            "operationName": "RenewToken",
            "variables": {
                "authToken": self._auth.authToken,
                "refreshToken": self._auth.refreshToken,
            },
        }

        self._auth = Authentication.from_dict(await self._query(query))

        await self._load_site_reference()

        return self._auth

    async def _load_site_reference(self):
        if self._auth is None:
            raise AuthRequiredException

        if self._country == FrankCountry.Belgium and self._siteReference is None:
            me = await self.user()
            self._siteReference = me.siteReference
        else:
            return

    async def month_summary(self) -> MonthSummary:
        """Get month summary data."""
        if self._auth is None:
            raise AuthRequiredException

        await self._load_site_reference()

        queries = {
            FrankCountry.Netherlands: {
                "query": """
                query MonthSummary {
                    monthSummary {
                        actualCostsUntilLastMeterReadingDate
                        expectedCostsUntilLastMeterReadingDate
                        expectedCosts
                        lastMeterReadingDate
                    }
                }
            """,
                "operationName": "MonthSummary",
                "variables": {},
            },
            FrankCountry.Belgium: {
                "query": "query MonthSummary($siteReference: String!) {\n  monthSummary(siteReference: $siteReference) {\n    _id\n    lastMeterReadingDate\n    expectedCostsUntilLastMeterReadingDate\n    actualCostsUntilLastMeterReadingDate\n    meterReadingDayCompleteness\n    gasExcluded\n  }\n}\n",
                "variables": {"siteReference": self._siteReference},
                "operationName": "MonthSummary",
            },
        }

        query_data = queries[self._country]

        return MonthSummary.from_dict(await self._query(query_data))

    async def invoices(self) -> Invoices:
        """Get invoices data.

        Returns a Invoices object, containing the previous, current and upcoming invoice.
        """
        if self._auth is None:
            raise AuthRequiredException

        await self._load_site_reference()

        queries = {
            FrankCountry.Netherlands: {
                "query": """
                query Invoices {
                    invoices {
                        previousPeriodInvoice {
                            StartDate
                            PeriodDescription
                            TotalAmount
                        }
                        currentPeriodInvoice {
                            StartDate
                            PeriodDescription
                            TotalAmount
                        }
                        upcomingPeriodInvoice {
                            StartDate
                            PeriodDescription
                            TotalAmount
                        }
                    }
                }
            """,
                "operationName": "Invoices",
                "variables": {},
            },
            FrankCountry.Belgium: {
                "query": "query Invoices($siteReference: String!) {\n  invoices(siteReference: $siteReference) {\n    _id\n    previousPeriodInvoice {\n      id\n      StartDate\n      PeriodDescription\n      TotalAmount\n      __typename\n    }\n    currentPeriodInvoice {\n      id\n      StartDate\n      PeriodDescription\n      TotalAmount\n      __typename\n    }\n    upcomingPeriodInvoice {\n      id\n      StartDate\n      PeriodDescription\n      TotalAmount\n      __typename\n    }\n    allInvoices {\n      id\n      StartDate\n      PeriodDescription\n      TotalAmount\n      __typename\n    }\n    __typename\n  }\n}",
                "variables": {"siteReference": self._siteReference},
                "operationName": "Invoices",
            },
        }

        query_data = queries[self._country]

        return Invoices.from_dict(await self._query(query_data))

    async def user(self) -> User:
        """Get user data."""
        if self._auth is None:
            raise AuthRequiredException

        queries = {
            FrankCountry.Netherlands: {
                "query": """
                query Me {
                    me {
                        ...UserFields
                    }
                }
                fragment UserFields on User {
                    id
                    connectionsStatus
                    firstMeterReadingDate
                    lastMeterReadingDate
                    advancedPaymentAmount
                    treesCount
                    hasCO2Compensation
                }
            """,
                "operationName": "Me",
                "variables": {},
            },
            FrankCountry.Belgium: {
                "query": "query Me($siteReference: String) {\n  me {\n    ...UserFields\n  }\n}\n\nfragment UserFields on User {\n  id\n  email\n  countryCode\n  advancedPaymentAmount(siteReference: $siteReference)\n  treesCount\n  hasInviteLink\n  hasCO2Compensation\n  notification\n  createdAt\n  deliverySites {\n    reference }\n}\n",
                "variables": {"siteReference": None},
                "operationName": "Me",
            },
        }

        query = queries[self._country]

        return User.from_dict(await self._query(query))

    async def prices(
        self, start_date: date, end_date: date | None = None
    ) -> MarketPrices:
        """Get market prices."""

        queries = {
            FrankCountry.Netherlands: {
                "query": """
                    query MarketPrices($startDate: Date!, $endDate: Date!) {
                        marketPricesElectricity(startDate: $startDate, endDate: $endDate) {
                        from
                        till
                        marketPrice
                        marketPriceTax
                        sourcingMarkupPrice
                        energyTaxPrice
                        }
                        marketPricesGas(startDate: $startDate, endDate: $endDate) {
                        from
                        till
                        marketPrice
                        marketPriceTax
                        sourcingMarkupPrice
                        energyTaxPrice
                        }
                    }
                """,
                "variables": {"startDate": str(start_date), "endDate": str(end_date)},
                "operationName": "MarketPrices",
            },
            FrankCountry.Belgium: {
                "query": "query MarketPrices($date: String!) {\n  marketPrices(date: $date) {\n    electricityPrices {\n      from\n      till\n      marketPrice\n      marketPriceTax\n      sourcingMarkupPrice\n      energyTaxPrice\n      perUnit\n    }\n    gasPrices {\n      from\n      till\n      marketPrice\n      marketPriceTax\n      sourcingMarkupPrice\n      energyTaxPrice\n      perUnit\n    }\n  }\n}\n",
                "variables": {"date": str(start_date)},
                "operationName": "MarketPrices",
            },
        }

        query_data = queries[self._country]

        return MarketPrices.from_dict(await self._query(query_data))

    async def user_prices(self, start_date: date) -> MarketPrices:
        """Get customer market prices."""
        if self._auth is None:
            raise AuthRequiredException

        await self._load_site_reference()

        queries = {
            FrankCountry.Netherlands: {
                "query": """
                query CustomerMarketPrices($date: String!) {
                    customerMarketPrices(date: $date) {
                        electricityPrices {
                            from
                            till
                            marketPrice
                            marketPriceTax
                            sourcingMarkupPrice: consumptionSourcingMarkupPrice
                            energyTaxPrice: energyTax
                        }
                        gasPrices {
                            from
                            till
                            marketPrice
                            marketPriceTax
                            sourcingMarkupPrice: consumptionSourcingMarkupPrice
                            energyTaxPrice: energyTax
                        }
                    }
                }
            """,
                "variables": {"date": str(start_date)},
                "operationName": "CustomerMarketPrices",
            },
            FrankCountry.Belgium: {
                "query": "query MarketPrices($date: String!, $siteReference: String!) {\n  customerMarketPrices(date: $date, siteReference: $siteReference) {\n    id\n    electricityPrices {\n      id\n      from\n      till\n      date\n      marketPrice\n      marketPriceTax\n      consumptionSourcingMarkupPrice\n      energyTax\n      perUnit\n    }\n    gasPrices {\n      id\n      from\n      till\n      date\n      marketPrice\n      marketPriceTax\n      consumptionSourcingMarkupPrice\n      energyTax\n      perUnit\n    }\n  }\n}\n",
                "variables": {
                    "siteReference": self._siteReference,
                    "date": str(start_date),
                },
                "operationName": "MarketPrices",
            },
        }

        query_data = queries[self._country]

        return MarketPrices.from_userprices_dict(await self._query(query_data))

    @property
    def is_authenticated(self) -> bool:
        """Return if client is authenticated.

        Does not actually check if the token is valid.
        """
        return self._auth is not None

    def authentication_valid(self) -> bool:
        """Return if client is authenticated.

        Does not actually check if the token is valid.
        """
        if self._auth is None:
            return False
        return self._auth.authTokenValid()

    async def close(self) -> None:
        """Close client session."""
        if self._session and self._close_session:
            await self._session.close()

    async def __aenter__(self) -> FrankEnergie:
        """Async enter.

        Returns:
            The FrankEnergie object.
        """
        return self

    async def __aexit__(self, *_exc_info: Any) -> None:
        """Async exit.

        Args:
            _exc_info: Exec type.
        """
        await self.close()
