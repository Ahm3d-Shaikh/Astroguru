from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi import status, Request

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    friendly_errors = []
    for err in exc.errors():
        field = ".".join([str(loc) for loc in err["loc"] if loc != "body"])
        msg = err["msg"]

        if err.get("type") == "value_error.missing":
            friendly_msg = f"'{field}' is required."
        elif err.get("type") == "type_error.enum":
            expected = err.get("ctx", {}).get("expected")
            friendly_msg = f"'{field}' must be {expected}."
        else:
            friendly_msg = f"{field}: {msg}"

        friendly_errors.append(friendly_msg)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"errors": friendly_errors},
    )