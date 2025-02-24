# terraform-yc-cost
Resource cost estimation from Terraform plan for Yandex Cloud.

List of supported resources:
```
yandex_compute_instance
yandex_compute_instance_group
yandex_compute_disk
yandex_compute_filesystem
yandex_kubernetes_cluster
yandex_kubernetes_node_group
yandex_mdb_mysql_cluster
yandex_mdb_postgresql_cluster
yandex_mdb_clickhouse_cluster
yandex_mdb_greenplum_cluster
yandex_mdb_kafka_cluster
yandex_mdb_redis_cluster
yandex_mdb_opensearch_cluster
yandex_ydb_database_dedicated
yandex_vpc_address
```

> Only `ru-central` Yandex Cloud installation is currently supported. The output is in RUB currency.

# Demo

Prerequisites:
- jq
- curl
- Terraform plan

Generate JSON file from Terraform plan:
```
terraform plan -out=plan.tfplan > /dev/null && terraform show -json plan.tfplan > plan.json
```

Send the plan to get cost estimation results:
```
curl -H "Content-Type: application/json" "https://tf.kirsh.cloud" -d @plan.json | jq
```

Result should look like this:
```
{
  "hourly": 441.69,
  "monthly": 328619.71,
  "currency": "RUB"
}
```
You can also get the full results like this:
```
curl -H "Content-Type: application/json" "https://tf.kirsh.cloud?full=true" -d @plan.json | jq
```
Which should look like this:
```
{
  "hourly": 514.58,
  "monthly": 382844.5,
  "currency": "RUB",
  "usage": [
    {
      "SKU": "dn27ajm6m8mnfcshbi61",
      "Description": "Fast network storage (SSD)",
      "Amount": 10,
      "Cost(RUB)": "0.17",
      "Unit": "gbyte*hour",
      "Resource Name": "vm-disk-1",
      "Resource Type": "yandex_compute_disk"
    },
    {
      "SKU": "dn27ajm6m8mnfcshbi61",
      "Description": "Fast network storage (SSD)",
      "Amount": 100,
      "Cost(RUB)": "1.65",
      "Unit": "gbyte*hour",
      "Resource Name": "default",
      "Resource Type": "yandex_compute_filesystem"
    },
    ...
}
```

# Deployment

## SKU

For the script to work you need to get SKU data like this:

```
cd functions
python get-sku.py $(yc iam create-token)
```
This will generate `sku.json` required for the script to work.

> You need YC CLI installed and initialized.

## Local

You can run the script locally like this:
```
cd functions
python app.py /path/plan.json
```
This will print the cost estimations in table format.

> Python `tabulate` package is required.

## Cloud

You can deploy this code as a Cloud Function in Yandex Cloud using Terraform module provided.

- Create a service account with `editor` role in cloud folder (or with more specific roles, if needed).
- Create `key.json` file for service account authentication.
- Alternatively, use OAuth authentication in Terraform provider.
- Provide `cloud_id` and `folder_id` as required in `variables.tf`.

Deploy terraform module:
```
cd terraform
terraform init
terraform apply
```

This will create a Cloud Function and an API Gateway for access.

You can send the requests to the API Gateway FQDN, as described in the Demo section.