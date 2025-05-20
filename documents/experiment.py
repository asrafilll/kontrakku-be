from django.db.models import Q

from .methods import process_contract
from .models import Contract


def run_process_latest_contract():
    contract = (
        Contract.objects.filter(
            Q(summarized_text__exact="") | Q(summarized_text__isnull=True)
        )
        .order_by("-id")
        .first()
    )
    if not contract:
        print("No pending contracts found.")
        return

    print(f"Processing contract ID: {contract.id}")
    process_contract(contract.id)
