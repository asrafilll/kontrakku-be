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


# from documents.methods import process_contract
# process_contract("970ace92-9513-425f-866b-3f8d8fb3597e")
