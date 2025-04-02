import datetime
import json
from typing import Annotated, List

import numpy as np
import pandas as pd
import pandas_datareader as pdr
import yfinance as yf
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import BedrockAgentResolver
from aws_lambda_powertools.event_handler.openapi.params import Body, Query
from aws_lambda_powertools.utilities.typing import LambdaContext
from duckduckgo_search import DDGS

tracer = Tracer()
logger = Logger()
app = BedrockAgentResolver()


@app.get(
    "/web_search",
    description="Searches the web using DuckDuckGo and returns the search results",
    operation_id="webSearch",
)
def web_search(
    query: Annotated[str, Query(description="The search query")],
    max_results: Annotated[
        int, Query(description="Max number of results to return. Default 10")
    ] = 10,
) -> Annotated[str, Body(description="The search results")]:
    "Searches the web using DuckDuckGo and returns the search results."
    ddgs = DDGS()
    results = ddgs.text(query, max_results=max_results)

    if len(results) == 0:
        raise Exception("No results found! Try a less restrictive/shorter query.")

    processed_results = [
        f"[{result['title']}]({result['href']})\n{result['body']}" for result in results
    ]

    formatted_results = "## Search Results\n\n" + "\n\n".join(processed_results)

    return formatted_results


@app.get(
    "/get_current_date",
    description="Returns the current date",
    operation_id="getCurrentDate",
)
def get_current_date() -> (
    Annotated[str, Body(description="The current date in YYYY-MM-DD format")]
):
    return datetime.datetime.now().strftime("%Y-%m-%d")


@app.get(
    "/get_ticker_data",
    description="Downloads historical stock data from Yahoo Finance and returns it as a dictionary",
    operation_id="getTickerData",
)
def get_ticker_data(
    tickers: Annotated[
        str,
        Query(
            description="A stock ticker symbol",
            examples=["AAPL", "MSFT"],
            alias="ticker",
        ),
    ],
    start_date: Annotated[
        str,
        Query(
            description="The start date for the data in YYYY-MM-DD format",
            examples=["2023-01-01"],
        ),
    ],
    end_date: Annotated[
        str, Query(description="The end date for the data in YYYY-MM-DD format")
    ],
    metric: Annotated[
        str,
        Query(
            description="The metric to return e.g., (Open, High, Low, Close, Volume)",
            examples=["Close", "all", "Open", "High", "Low", "Volume"],
        ),
    ] = "all",
    sampling: Annotated[
        str,
        Query(
            description="The frequency of the data",
            examples=["daily", "weekly", "monthly"],
        ),
    ] = "monthly",
) -> Annotated[
    dict,
    Body(
        description="A dictionary where keys are ticker symbols and values are lists of historical data records"
    ),
]:
    """Downloads historical stock data from Yahoo Finance and returns it as a dictionary."""

    tickers = [tickers]

    df = yf.download(tickers, start=start_date, end=end_date)

    if metric != "all":
        df = df[metric]

    if sampling == "weekly":
        df = df.resample("W-SAT").last()
    elif sampling == "monthly":
        df = df.resample("ME").last()
    elif sampling == "quarterly":
        df = df.resample("QE").last()
    elif sampling == "daily":
        pass
    else:
        raise ValueError(
            "Invalid sampling frequency. Use 'daily', 'weekly', 'monthly', 'quarterly."
        )

    result = {}
    for ticker in tickers:
        if metric == "all":
            df_tick = df.loc[:, (slice(None), ticker)]
            df_tick.columns = df_tick.columns.droplevel("Ticker")
        else:
            df_tick = df.loc[:, ticker]
            df_tick = df_tick.to_frame(name=metric)
        df_tick = df_tick.reset_index()
        df_tick["Date"] = df_tick["Date"].dt.strftime("%Y-%m-%d")
        result[ticker] = df_tick.to_dict(orient="records")

    return result


@app.get(
    "/get_fred_data",
    description="Downloads data from the Federal Reserve Economic Data (FRED) database and returns it as dictionary",
    operation_id="getFredData",
)
def get_fred_data(
    series: Annotated[
        str,
        Query(description="The FRED series ID e.g., 'GDP'", examples=["GDP", "CPI"]),
    ],
    start_date: Annotated[
        str,
        Query(
            description="The start date for the data in YYYY-MM-DD format",
            examples=["2023-01-01"],
        ),
    ],
    end_date: Annotated[
        str, Query(description="The end date for the data in YYYY-MM-DD format")
    ],
    sampling: Annotated[
        str,
        Query(
            description="The frequency of the data e.g. daily, weekly, monthly",
            examples=["monthly", "quarterly", "yearly"],
        ),
    ] = "monthly",
) -> Annotated[
    list[dict],
    Body(
        description="A list of dictionaries containing 'Date' and the value of the FRED series"
    ),
]:
    """Downloads data from the Federal Reserve Economic Data (FRED) database and returns it as dictionary."""
    df = pdr.data.DataReader(series, start=start_date, end=end_date, data_source="fred")

    if sampling == "monthly":
        df = df.resample("ME").last()
    elif sampling == "quarterly":
        df = df.resample("QE").last()
    elif sampling == "yearly":
        df = df.resample("YE").last()
    else:
        raise ValueError(
            "Invalid sampling frequency. Use 'monthly', 'quarterly', or 'yearly'."
        )

    df.reset_index(inplace=True)
    df["DATE"] = df["DATE"].dt.strftime("%Y-%m-%d")
    df.rename(columns={"DATE": "Date"}, inplace=True)

    result = df.to_dict(orient="records")

    return result


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext):
    return app.resolve(event, context)


if __name__ == "__main__":
    from pathlib import Path

    (Path(__file__).parent.parent / "api_schema.json").write_text(
        json.dumps(
            json.loads(app.get_openapi_json_schema(title="Stock Data API")), indent=2
        )
    )
