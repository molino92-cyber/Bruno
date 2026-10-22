"""Consulta opcional ao ViaCEP. Nenhum dado do cliente além do CEP é enviado."""
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from .domain import STATES


def lookup_postal_code(postal_code):
    raw = str(postal_code).strip()
    if not re.fullmatch(r"\d{5}-?\d{3}", raw):
        raise ValueError("Informe um CEP válido com 8 dígitos, como 69000-000.")
    code = raw.replace("-", "")
    request = Request(f"https://viacep.com.br/ws/{code}/json/", headers={"User-Agent": "DoceAtelie/1.2", "Accept": "application/json"})
    try:
        with urlopen(request, timeout=6) as response:
            payload = json.loads(response.read(32000).decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 400:
            raise ValueError("CEP inválido. Confira os 8 dígitos.") from exc
        raise ValueError("Não foi possível consultar o CEP agora. Preencha o endereço manualmente ou tente novamente.") from exc
    except (OSError, URLError, ValueError) as exc:
        raise ValueError("A consulta de CEP precisa de internet. Você pode preencher o endereço manualmente.") from exc
    if not isinstance(payload, dict) or payload.get("erro"):
        raise ValueError("CEP não encontrado. Confira o número ou preencha o endereço manualmente.")
    if payload.get("uf") not in STATES:
        raise ValueError("O serviço retornou um endereço incompleto. Preencha os campos manualmente.")
    return {"postal_code": code, "street": str(payload.get("logradouro", "")), "neighborhood": str(payload.get("bairro", "")),
            "city": str(payload.get("localidade", "")), "state": str(payload.get("uf", ""))}
