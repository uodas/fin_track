import pandera.pandas as pa
from pandera.typing import Series
from decimal import Decimal


class TransactionSchema(pa.DataFrameModel):
    date: Series[str] = pa.Field(coerce=True)
    amount: Series[object] = (
        pa.Field()
    )  # Use object to allow decimal.Decimal without strict scale
    description: Series[str] = pa.Field(nullable=True)
    note: Series[str] = pa.Field(nullable=True)
    hash_id: Series[str]

    @pa.check("amount")
    def check_is_decimal(cls, amount: Series) -> Series:
        return amount.apply(lambda x: isinstance(x, Decimal))

    class Config:
        strict = True
        coerce = True
