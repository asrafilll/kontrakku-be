from huey.contrib.djhuey import task
from .methods import process_contract


@task()
def process_contract_task(contract_id):
    result_summary = process_contract(contract_id)
    return result_summary