import argparse
import json
import logging
from tabulate import tabulate
from datetime import datetime
from collections import defaultdict

# Logging 
logging.getLogger().setLevel(logging.DEBUG)

# Open external files
with open('./sku.json') as f:
    prices  = json.load(f)

with open('./mdb.json') as f:
    mdb     = json.load(f)

# Usage data
usage       = []

def add_usage(sku, amount, tf_resource_name, tf_resource_type):
    usage.append({"sku": sku, "amount": amount, "resource_name": tf_resource_name, "resource_type": tf_resource_type})

def print_usage():
    table_data = []
    headers = ["SKU", "Description", "Amount", "Cost(RUB)", "Unit", "Resource Name", "Resource Type"]

    summary = defaultdict(lambda: {"amount": 0, "cost": 0.0})

    for item in usage:
        sku = item.get("sku")
        full_name = get_sku_name(sku, prices)
        amount = item.get("amount")
        cost = get_latest_price(sku, prices) * amount
        unit = get_sku_unit(sku, prices)
        resource_name = item.get("resource_name")
        resource_type = item.get("resource_type")

        key = (sku, full_name, unit, resource_name, resource_type)
        summary[key]["amount"] += amount
        summary[key]["cost"] += cost

    for key, value in summary.items():
        sku, full_name, unit, resource_name, resource_type = key
        row = [
            sku,
            full_name,
            value["amount"],
            f"{value['cost']:.2f}",
            unit,
            resource_name,
            resource_type
        ]
        table_data.append(row)

    print(tabulate(table_data, headers=headers, tablefmt="grid"))

def get_usage():
    summary = defaultdict(lambda: {"amount": 0, "cost": 0.0})

    for item in usage:
        sku = item.get("sku")
        full_name = get_sku_name(sku, prices)
        amount = item.get("amount")
        cost = get_latest_price(sku, prices) * amount
        unit = get_sku_unit(sku, prices)
        resource_name = item.get("resource_name")
        resource_type = item.get("resource_type")

        key = (sku, full_name, unit, resource_name, resource_type)
        summary[key]["amount"] += amount
        summary[key]["cost"] += cost
    
    # Convert the summary to a list of dictionaries
    result = []
    for key, value in summary.items():
        sku, full_name, unit, resource_name, resource_type = key
        result.append({
            "SKU": sku,
            "Description": full_name,
            "Amount": value["amount"],
            "Cost(RUB)": f"{value['cost']:.2f}",
            "Unit": unit,
            "Resource Name": resource_name,
            "Resource Type": resource_type
        })

    return result

# Get data from sku
def get_latest_price(sku_id, prices):
    for sku in prices['skus']:
        if sku['id'] == sku_id:
            latest_pricing_version = max(sku['pricingVersions'], key=lambda x: x['effectiveTime'])
            latest_price = latest_pricing_version['pricingExpressions'][0]['rates'][0]['unitPrice']
            return float(latest_price)
    return 0

def get_sku_name(sku_id, prices):
    for sku in prices['skus']:
        if sku['id'] == sku_id:
            return sku['name']
    return 0

def get_sku_unit(sku_id, prices):
    for sku in prices['skus']:
        if sku['id'] == sku_id:
            return sku['pricingUnit']
    return 0

# Calculate total
def calculate_total(data, prices):
    total = 0
    for item in data:
        sku_id = item['sku']
        amount = item['amount']
        latest_price = get_latest_price(sku_id, prices)
        total += amount * latest_price
        logging.info(f"{sku_id} - {amount * latest_price * 24 * 30}")
    return total

# Get resources data for MDB
def get_mdb_preset(service_type, preset_id):
    service_data = mdb.get(service_type)
    if not service_data:
        raise ValueError(f"Service type '{service_type}' not found in the data structure")
    
    preset_data = service_data.get(preset_id)
    if not preset_data:
        raise ValueError(f"Preset ID '{preset_id}' not found in service type '{service_type}'")
    
    cores = preset_data.get("cores")
    core_fraction = preset_data.get("core_fraction")
    memory = preset_data.get("memory")
    
    if preset_id.startswith("s1") or preset_id.startswith("b1") or preset_id.startswith("hm1"):
        platform_id = "standard-v1"
    elif preset_id.startswith("s2") or preset_id.startswith("b2") or preset_id.startswith("m2") or preset_id.startswith("hm2") or preset_id.startswith("i2"):
        platform_id = "standard-v2"
    elif preset_id.startswith("s3") or preset_id.startswith("m3") or preset_id.startswith("c3") or preset_id.startswith("hm3") or preset_id.startswith("i3"):
        platform_id = "standard-v3"
    elif preset_id.startswith("s3f") or preset_id.startswith("m3f") or preset_id.startswith("c3f") or preset_id.startswith("i3f"): 
        platform_id = "highfreq-v3" #! в таблице sku не хватает данных
    else:
        platform_id = None

    return cores, core_fraction, memory, platform_id

### 
### Per service functions
###

# yandex_compute_instance
def process_vm(resource): #! дополнить диски и GPU
    resource_type       = resource["type"]
    resource_name       = resource["name"]
    resource_values     = resource["values"]

    platform_id         = resource_values.get("platform_id", "standard-v3")
    cores               = resource_values["resources"][0]["cores"]
    core_fraction       = resource_values["resources"][0].get("core_fraction", 100)
    memory              = resource_values["resources"][0]["memory"]
    gpus                = resource_values["resources"][0]["gpus"]
    scheduling_policy   = resource_values.get("scheduling_policy", [{}])
    preemptible         = scheduling_policy[0].get("preemptible", False)
    network_nat         = resource_values["network_interface"][0].get("nat", False) #! проверить несколько интерфейсов
    boot_disk_size      = resource_values["boot_disk"][0]["initialize_params"][0].get("size", 0)
    boot_disk_type      = resource_values["boot_disk"][0]["initialize_params"][0].get("type", "network-hdd")

    if(platform_id == "standard-v3"):
        # preemptible
        if(preemptible == True):
            # cpu
            if(core_fraction == 100):
                add_usage("dn2e2fphfupugm21k4hv", cores, resource_name, resource_type) # Intel Ice Lake. 100% vCPU \u2014 preemptible instances [core*hour]
            if(core_fraction == 50):
                add_usage("dn2333h2iv190t06bon8", cores, resource_name, resource_type) # Intel Ice Lake. 50% vCPU \u2014 preemptible instances [core*hour]
            if(core_fraction == 20):
                add_usage("dn2pdedm5fon78kbl0fh", cores, resource_name, resource_type) # Intel Ice Lake. 20% vCPU \u2014 preemptible instances [core*hour]
            # ram
            add_usage("dn26ur5frjbgdek2a0g5", memory, resource_name, resource_type) # Intel Ice Lake. RAM \u2014 preemptible instances [gbyte*hour]
            
        # non preemptible
        if(preemptible == False):
            # cpu
            if(core_fraction == 100):
                add_usage("dn2k3vqlk9snp1jv351u", cores, resource_name, resource_type) # Intel Ice Lake. 100% vCPU [core*hour]
            if(core_fraction == 50):
                add_usage("dn2f0q0d6gtpcom4b1p6", cores, resource_name, resource_type) # Intel Ice Lake. 50% vCPU [core*hour]
            if(core_fraction == 20):
                add_usage("dn2r8aklo79bmpkd87l3", cores, resource_name, resource_type) # Intel Ice Lake. 20% vCPU [core*hour]
            # ram
            add_usage("dn2ilq72mjc3bej6j74p", memory, resource_name, resource_type) # Intel Ice Lake. RAM [gbyte*hour]

    if(platform_id == "standard-v2"):
        # preemptible
        if(preemptible == True):
            # cpu
            if(core_fraction == 100):
                add_usage("dn2ipnaa10sls6i7osfv", cores, resource_name, resource_type) # Intel Cascade Lake. 100% vCPU \u2014 preemptible instances [core*hour]
            if(core_fraction == 50):
                add_usage("dn20jng1b3a6ggtn52bo", cores, resource_name, resource_type) # Intel Cascade Lake. 50% vCPU \u2014 preemptible instances [core*hour]
            if(core_fraction == 20):
                add_usage("dn2krclp8uj3432vmpre", cores, resource_name, resource_type) # Intel Cascade Lake. 20% vCPU \u2014 preemptible instances [core*hour]
            if(core_fraction == 5):
                add_usage("dn292ebti5dcjio7vh2s", cores, resource_name, resource_type) # Intel Cascade Lake. 5% vCPU \u2014 preemptible instances [core*hour]
            # ram
            add_usage("dn26ur5frjbgdek2a0g5", memory, resource_name, resource_type) # Intel Ice Lake. RAM \u2014 preemptible instances [gbyte*hour]
            
        # non preemptible
        if(preemptible == False):
            # cpu
            if(core_fraction == 100):
                add_usage("dn218a07u143r9v1r5ms", cores, resource_name, resource_type) # Intel Cascade Lake. 100% vCPU [core*hour]
            if(core_fraction == 50):
                add_usage("dn2qbqi1am9oq6oc9s05", cores, resource_name, resource_type) # Intel Cascade Lake. 50% vCPU [core*hour]
            if(core_fraction == 20):
                add_usage("dn26skitjdon841jqit7", cores, resource_name, resource_type) # Intel Cascade Lake. 20% vCPU [core*hour]
            if(core_fraction == 5):
                add_usage("dn2l09d8brnv9s8m5p2r", cores, resource_name, resource_type) # Intel Cascade Lake. 5% vCPU [core*hour]
            # ram
            add_usage("dn2fhtcoocq50j1uj4tg", memory, resource_name, resource_type) # Intel Cascade Lake. RAM [gbyte*hour]
    
    if(platform_id == "standard-v1"):
        # preemptible
        if(preemptible == True):
            # cpu
            if(core_fraction == 100):
                add_usage("dn247qigcq66fq6t3tk5", cores, resource_name, resource_type) # Intel Broadwell. 100% vCPU \u2014 preemptible instances [core*hour]
            if(core_fraction == 20):
                add_usage("dn24sf8vh5cvj53voa7k", cores, resource_name, resource_type) # Intel Broadwell. 20% vCPU \u2014 preemptible instances [core*hour]
            if(core_fraction == 5):
                add_usage("dn2g5qo1211n5k8i1s3v", cores, resource_name, resource_type) # Intel Broadwell. 5% vCPU \u2014 preemptible instances [core*hour]
            # ram
            add_usage("dn2u497ok1kl70on0ta2", memory, resource_name, resource_type) # Intel Broadwell. RAM \u2014 preemptible instances [gbyte*hour]
            
        # non preemptible
        if(preemptible == False):
            # cpu
            if(core_fraction == 100):
                add_usage("dn299ll54t5jt2gojh7e", cores, resource_name, resource_type) # Intel Broadwell. 100% vCPU [core*hour]
            if(core_fraction == 20):
                add_usage("dn2vmq6na03r9vlds7j8", cores, resource_name, resource_type) # Intel Broadwell. 20% vCPU [core*hour]
            if(core_fraction == 5):
                add_usage("dn2pm2gap1cc09a33s06", cores, resource_name, resource_type) # Intel Broadwell. 5% vCPU [core*hour]
            # ram
            add_usage("dn2dka206olokggsieuu", memory, resource_name, resource_type) # Intel Broadwell. RAM [gbyte*hour]
    
    if(platform_id == "highfreq-v3"): #! нет данных в биллинг апи
        # cpu
        add_usage("no_sku_id", cores, resource_name, resource_type) # Intel Ice Lake (Compute Optimized). 100% vCPU [core*hour]
        # ram
        add_usage("no_sku_id", memory, resource_name, resource_type) # Intel Ice Lake (Compute Optimized). RAM [gbyte*hour]

    if(platform_id == "standard-v3-t4"):
        # preemptible
        if(preemptible == True):
            # cpu
            add_usage("dn2lsfskfirek2985fnd", cores, resource_name, resource_type) # Intel Ice Lake with Nvidia T4. 100% vCPU \u2014 preemptible instances [core*hour]
            # ram
            add_usage("dn2im0g43iedeohe4sac", memory, resource_name, resource_type) # Intel Ice Lake with Nvidia T4. RAM - preemptible instances [gbyte*hour]
            # gpu
            add_usage("dn2cpk4mc82b1vib72e5", gpus, resource_name, resource_type) # Intel Ice Lake with Nvidia T4. GPU - preemptible instances [gpus*hour]
            
        # non preemptible
        if(preemptible == False):
            # cpu
            add_usage("dn24b7m6qol7tb7tukga", cores, resource_name, resource_type) # Intel Ice Lake with Nvidia T4. 100% vCPU [core*hour]
            # ram
            add_usage("dn2lg2hrvbn5b8lm7em4", memory, resource_name, resource_type) # Intel Ice Lake with Nvidia T4. RAM [gbyte*hour]
            # gpu
            add_usage("dn20ml8ifdps6m7048an", gpus, resource_name, resource_type) # Intel Ice Lake with Nvidia T4. GPU [gpus*hour]
    
    if(platform_id == "standard-v3-t4i"):
        # preemptible
        if(preemptible == True):
            # cpu
            add_usage("dn2960mi7268n67o8iae", cores, resource_name, resource_type) # Intel Ice lake with t4i. 100% vCPU - preemptible instances [core*hour]
            # ram
            add_usage("dn25rffeums4j1ku5649", memory, resource_name, resource_type) # Intel Ice lake with t4i. RAM - preemptible instances [gbyte*hour]
            # gpu
            add_usage("dn2qlml2u48bng4jgilh", gpus, resource_name, resource_type) # Intel Ice lake with t4i. GPU - preemptible instances [gpus*hour]
            
        # non preemptible
        if(preemptible == False):
            # cpu
            add_usage("dn242l2ivnhdd5so2oga", cores, resource_name, resource_type) # Intel Ice lake with t4i. 100% vCPU [core*hour]
            # ram
            add_usage("dn290pbmohupnus9ajb7", memory, resource_name, resource_type) # Intel Ice lake with t4i. RAM [gbyte*hour]
            # gpu
            add_usage("dn2hql9evci880d8jq7i", gpus, resource_name, resource_type) # Intel Ice lake with t4i. GPU" [gpus*hour]

    if(platform_id == "gpu-standard-v3"):
        # preemptible
        if(preemptible == True):
            # cpu
            add_usage("dn2tvs05nnrib706hgnt", cores, resource_name, resource_type) # AMD Epyc with Nvidia A100. 100% vCPU - preemptible instances [core*hour]
            # ram
            add_usage("dn2m4gusa7m7t4hl6vo2", memory, resource_name, resource_type) # AMD Epyc with Nvidia A100. RAM \u2014 preemptible instances [gbyte*hour]
            # gpu
            add_usage("dn211dses9ju3abvq0bs", gpus, resource_name, resource_type) # AMD Epyc with Nvidia A100. GPU - preemptible instances [gpus*hour]
            
        # non preemptible
        if(preemptible == False): 
            # cpu
            add_usage("dn28c1erut6m9f9uem08", cores, resource_name, resource_type) # AMD Epyc with Nvidia A100. 100% vCPU [core*hour]
            # ram
            add_usage("dn21jcm82510bfa6is22", memory, resource_name, resource_type) # AMD Epyc with Nvidia A100. RAM [gbyte*hour]
            # gpu
            add_usage("dn2395q10bihjmm2b0v6", gpus, resource_name, resource_type) # AMD Epyc with Nvidia A100. GPU [gpus*hour]

    if(platform_id == "gpu-standard-v3i"):
        # preemptible
        if(preemptible == True):
            # cpu
            add_usage("dn2o9fiqemifmch1dq7c", cores, resource_name, resource_type) # AMD Epyc 9474F with Gen2. 100% vCPU - preemptible instances [core*hour]
            # ram
            add_usage("dn2mgiub24223fh5mvgv", memory, resource_name, resource_type) # AMD Epyc 9474F with Gen2. RAM - preemptible instances [gbyte*hour]
            # gpu
            add_usage("dn2qvcfe8i5vqlrvterc", gpus, resource_name, resource_type) # AMD Epyc 9474F with Gen2. GPU - preemptible instances [gpus*hour]
            
        # non preemptible
        if(preemptible == False): 
            # cpu
            add_usage("dn2fd3g50rub98vfprlt", cores, resource_name, resource_type) # AMD Epyc 9474F with Gen2. 100% vCPU [core*hour]
            # ram
            add_usage("dn2h5gi2u2l3bdclrput", memory, resource_name, resource_type) # AMD Epyc 9474F with Gen2. RAM [gbyte*hour]
            # gpu
            add_usage("dn2jfrjoic5h3nh7e6jh", gpus, resource_name, resource_type) # AMD Epyc 9474F with Gen2. GPU [gpus*hour]
    
    if(platform_id == "gpu-standard-v2"):
        # preemptible
        if(preemptible == True):
            # cpu
            add_usage("dn2h4u30djq3jhh8dqh8", cores, resource_name, resource_type) # Intel Cascade Lake with Nvidia Tesla v100. 100% vCPU - preemptible instances [core*hour]
            # ram
            add_usage("dn2hotj7skno0turhbq1", memory, resource_name, resource_type) # Intel Cascade Lake with Nvidia Tesla v100. RAM \u2014 preemptible instances [gbyte*hour]
            # gpu
            add_usage("dn23ppvthcls7rjt5pol", gpus, resource_name, resource_type) # Intel Cascade Lake with Nvidia Tesla v100. GPU - preemptible instances [gpus*hour]
            
        # non preemptible
        if(preemptible == False):
            # cpu
            add_usage("dn2udmu2aa9jm5a8f4ug", cores, resource_name, resource_type) # Intel Cascade Lake with Nvidia Tesla v100. 100% vCPU [core*hour]
            # ram
            add_usage("dn2qtp90p3r8l8vakmm6", memory, resource_name, resource_type) # Intel Cascade Lake with Nvidia Tesla v100. RAM [gbyte*hour]
            # gpu
            add_usage("dn2dlvuk2ecf6hu0kjtl", gpus, resource_name, resource_type) # Intel Cascade Lake with Nvidia Tesla v100. GPU [gpus*hour]

    if(platform_id == "gpu-standard-v1"):
        # preemptible
        if(preemptible == True):
            # cpu
            add_usage("dn2t7aa68lehsmvo5mss", cores, resource_name, resource_type) # Intel Broadwell with Nvidia Tesla v100. 100% vCPU - preemptible instances [core*hour]
            # ram
            add_usage("dn2k0omvmglh857u60vu", memory, resource_name, resource_type) # Intel Broadwell with Nvidia Tesla v100. RAM - preemptible instances [gbyte*hour]
            # gpu
            add_usage("dn2lov15qqamcimfv84q", gpus, resource_name, resource_type) # Intel Broadwell with Nvidia Tesla v100. GPU - preemptible instances [gpus*hour]
            
        # non preemptible
        if(preemptible == False):
            # cpu
            add_usage("dn2sfcnkn3jlhmq568ac", cores, resource_name, resource_type) # Intel Broadwell with Nvidia Tesla v100. 100% vCPU [core*hour]
            # ram
            add_usage("dn2nccae8nra81iqphdn", memory, resource_name, resource_type) # Intel Broadwell with Nvidia Tesla v100. RAM [gbyte*hour]
            # gpu
            add_usage("dn2oroscvvtb6sqtt83i", gpus, resource_name, resource_type) # Intel Broadwell with Nvidia Tesla v100. GPU [gpus*hour]
    
    if(boot_disk_size > 0):
        if(boot_disk_type == "network-ssd"):
            add_usage("dn27ajm6m8mnfcshbi61", boot_disk_size, resource_name, resource_type) # Fast network storage (SSD) [gbyte*hour]
        
        if(boot_disk_type == "network-hdd"):
            add_usage("dn2al287u6jr3a710u8g", boot_disk_size, resource_name, resource_type) # Standard network storage (HDD) [gbyte*hour]

        if(boot_disk_type == "network-ssd-nonreplicated"):
            add_usage("dn24kdllggk8ahsol15g", boot_disk_size, resource_name, resource_type) # Non-replicated fast network storage (SSD) [gbyte*hour]

        if(boot_disk_type == "network-ssd-io-m3"):
            add_usage("dn25ksor7p112bvs2qts", boot_disk_size, resource_name, resource_type) # Ultra fast network storage with 3 replicas (SSD) [gbyte*hour]

    if(network_nat):
        add_usage("dn229q5mnmp58t58tfel", 1, resource_name, resource_type) # Public IP address [fip*hour]

    logging.debug(json.dumps(resource_values, indent=4).replace('\n', '\r'))
    return 0

# yandex_compute_disk
def process_vm_disk(resource):
    resource_type       = resource["type"]
    resource_name       = resource["name"]
    resource_values     = resource["values"]

    disk_size           = resource_values.get("size", 0)
    disk_type           = resource_values.get("type", "network-hdd")

    if(disk_size > 0):
        if(disk_type == "network-hdd"):
            add_usage("dn2al287u6jr3a710u8g", disk_size, resource_name, resource_type) # Standard network storage (HDD) [gbyte*hour]
        if(disk_type == "network-ssd"):
            add_usage("dn27ajm6m8mnfcshbi61", disk_size, resource_name, resource_type) # Fast network storage (SSD) [gbyte*hour]
        if(disk_type == "network-ssd-nonreplicated"):
            add_usage("dn24kdllggk8ahsol15g", disk_size, resource_name, resource_type) # Non-replicated fast network storage (SSD) [gbyte*hour]
        if(disk_type == "network-ssd-io-m3"): 
            add_usage("dn25ksor7p112bvs2qts", disk_size, resource_name, resource_type) # Ultra fast network storage with 3 replicas (SSD) [gbyte*hour]

    logging.debug(json.dumps(resource_values, indent=4).replace('\n', '\r'))
    return 0

# yandex_compute_instance_group
def process_vm_group(resource):
    resource_type       = resource["type"]
    resource_name       = resource["name"]
    resource_values     = resource["values"]

    auto_scale          = resource_values["scale_policy"][0].get("auto_scale", [])
    fixed_scale         = resource_values["scale_policy"][0].get("fixed_scale", [])
    boot_disk_size      = resource_values["instance_template"][0]["boot_disk"][0].get("size", 0)
    boot_disk_type      = resource_values["instance_template"][0]["boot_disk"][0].get("type", "network-hdd")
    network_nat         = resource_values["instance_template"][0]["network_interface"][0].get("nat", False) #! проверить несколько интерфейсов
    platform_id         = resource_values["instance_template"][0]["platform_id"]
    cores               = resource_values["instance_template"][0]["resources"][0]["cores"]
    core_fraction       = resource_values["instance_template"][0]["resources"][0].get("core_fraction", 100)
    memory              = resource_values["instance_template"][0]["resources"][0]["memory"]
    gpus                = resource_values["instance_template"][0]["resources"][0]["gpus"]
    scheduling_policy   = resource_values.get("scheduling_policy", [{}])
    preemptible         = scheduling_policy[0].get("preemptible", False)

    if auto_scale:
        instance_num = auto_scale[0]["initial"]
    elif fixed_scale:
        instance_num = fixed_scale[0]["size"]

    if(platform_id == "standard-v3"):
        # preemptible
        if(preemptible == True):
            # cpu
            if(core_fraction == 100):
                add_usage("dn2e2fphfupugm21k4hv", cores * instance_num, resource_name, resource_type) # Intel Ice Lake. 100% vCPU \u2014 preemptible instances [core*hour]
            if(core_fraction == 50):
                add_usage("dn2333h2iv190t06bon8", cores * instance_num, resource_name, resource_type) # Intel Ice Lake. 50% vCPU \u2014 preemptible instances [core*hour]
            if(core_fraction == 20):
                add_usage("dn2pdedm5fon78kbl0fh", cores * instance_num, resource_name, resource_type) # Intel Ice Lake. 20% vCPU \u2014 preemptible instances [core*hour]
            # ram
            add_usage("dn26ur5frjbgdek2a0g5", memory * instance_num, resource_name, resource_type) # Intel Ice Lake. RAM \u2014 preemptible instances [gbyte*hour]
            
        # non preemptible
        if(preemptible == False):
            # cpu
            if(core_fraction == 100):
                add_usage("dn2k3vqlk9snp1jv351u", cores * instance_num, resource_name, resource_type) # Intel Ice Lake. 100% vCPU [core*hour]
            if(core_fraction == 50):
                add_usage("dn2f0q0d6gtpcom4b1p6", cores * instance_num, resource_name, resource_type) # Intel Ice Lake. 50% vCPU [core*hour]
            if(core_fraction == 20):
                add_usage("dn2r8aklo79bmpkd87l3", cores * instance_num, resource_name, resource_type) # Intel Ice Lake. 20% vCPU [core*hour]
            # ram
            add_usage("dn2ilq72mjc3bej6j74p", memory * instance_num, resource_name, resource_type) # Intel Ice Lake. RAM [gbyte*hour]

    if(platform_id == "standard-v2"):
        # preemptible
        if(preemptible == True):
            # cpu
            if(core_fraction == 100):
                add_usage("dn2ipnaa10sls6i7osfv", cores * instance_num, resource_name, resource_type) # Intel Cascade Lake. 100% vCPU \u2014 preemptible instances [core*hour]
            if(core_fraction == 50):
                add_usage("dn20jng1b3a6ggtn52bo", cores * instance_num, resource_name, resource_type) # Intel Cascade Lake. 50% vCPU \u2014 preemptible instances [core*hour]
            if(core_fraction == 20):
                add_usage("dn2krclp8uj3432vmpre", cores * instance_num, resource_name, resource_type) # Intel Cascade Lake. 20% vCPU \u2014 preemptible instances [core*hour]
            if(core_fraction == 5):
                add_usage("dn292ebti5dcjio7vh2s", cores * instance_num, resource_name, resource_type) # Intel Cascade Lake. 5% vCPU \u2014 preemptible instances [core*hour]
            # ram
            add_usage("dn26ur5frjbgdek2a0g5", memory * instance_num, resource_name, resource_type) # Intel Ice Lake. RAM \u2014 preemptible instances [gbyte*hour]
            
        # non preemptible
        if(preemptible == False):
            # cpu
            if(core_fraction == 100):
                add_usage("dn218a07u143r9v1r5ms", cores * instance_num, resource_name, resource_type) # Intel Cascade Lake. 100% vCPU [core*hour]
            if(core_fraction == 50):
                add_usage("dn2qbqi1am9oq6oc9s05", cores * instance_num, resource_name, resource_type) # Intel Cascade Lake. 50% vCPU [core*hour]
            if(core_fraction == 20):
                add_usage("dn26skitjdon841jqit7", cores * instance_num, resource_name, resource_type) # Intel Cascade Lake. 20% vCPU [core*hour]
            if(core_fraction == 5):
                add_usage("dn2l09d8brnv9s8m5p2r", cores * instance_num, resource_name, resource_type) # Intel Cascade Lake. 5% vCPU [core*hour]
            # ram
            add_usage("dn2fhtcoocq50j1uj4tg", memory * instance_num, resource_name, resource_type) # Intel Cascade Lake. RAM [gbyte*hour]
    
    if(platform_id == "standard-v1"):
        # preemptible
        if(preemptible == True):
            # cpu
            if(core_fraction == 100):
                add_usage("dn247qigcq66fq6t3tk5", cores * instance_num, resource_name, resource_type) # Intel Broadwell. 100% vCPU \u2014 preemptible instances [core*hour]
            if(core_fraction == 20):
                add_usage("dn24sf8vh5cvj53voa7k", cores * instance_num, resource_name, resource_type) # Intel Broadwell. 20% vCPU \u2014 preemptible instances [core*hour]
            if(core_fraction == 5):
                add_usage("dn2g5qo1211n5k8i1s3v", cores * instance_num, resource_name, resource_type) # Intel Broadwell. 5% vCPU \u2014 preemptible instances [core*hour]
            # ram
            add_usage("dn2u497ok1kl70on0ta2", memory * instance_num, resource_name, resource_type) # Intel Broadwell. RAM \u2014 preemptible instances [gbyte*hour]
            
        # non preemptible
        if(preemptible == False):
            # cpu
            if(core_fraction == 100):
                add_usage("dn299ll54t5jt2gojh7e", cores * instance_num, resource_name, resource_type) # Intel Broadwell. 100% vCPU [core*hour]
            if(core_fraction == 20):
                add_usage("dn2vmq6na03r9vlds7j8", cores * instance_num, resource_name, resource_type) # Intel Broadwell. 20% vCPU [core*hour]
            if(core_fraction == 5):
                add_usage("dn2pm2gap1cc09a33s06", cores * instance_num, resource_name, resource_type) # Intel Broadwell. 5% vCPU [core*hour]
            # ram
            add_usage("dn2dka206olokggsieuu", memory * instance_num, resource_name, resource_type) # Intel Broadwell. RAM [gbyte*hour]
    
    if(platform_id == "highfreq-v3"): #! нет данных в биллинг апи
        # cpu
        add_usage("no_sku_id", cores * instance_num, resource_name, resource_type) # Intel Ice Lake (Compute Optimized). 100% vCPU [core*hour]
        # ram
        add_usage("no_sku_id", memory * instance_num, resource_name, resource_type) # Intel Ice Lake (Compute Optimized). RAM [gbyte*hour]

    if(platform_id == "standard-v3-t4"):
        # preemptible
        if(preemptible == True):
            # cpu
            add_usage("dn2lsfskfirek2985fnd", cores * instance_num, resource_name, resource_type) # Intel Ice Lake with Nvidia T4. 100% vCPU \u2014 preemptible instances [core*hour]
            # ram
            add_usage("dn2im0g43iedeohe4sac", memory * instance_num, resource_name, resource_type) # Intel Ice Lake with Nvidia T4. RAM - preemptible instances [gbyte*hour]
            # gpu
            add_usage("dn2cpk4mc82b1vib72e5", gpus * instance_num, resource_name, resource_type) # Intel Ice Lake with Nvidia T4. GPU - preemptible instances [gpus*hour]
            
        # non preemptible
        if(preemptible == False):
            # cpu
            add_usage("dn24b7m6qol7tb7tukga", cores * instance_num, resource_name, resource_type) # Intel Ice Lake with Nvidia T4. 100% vCPU [core*hour]
            # ram
            add_usage("dn2lg2hrvbn5b8lm7em4", memory * instance_num, resource_name, resource_type) # Intel Ice Lake with Nvidia T4. RAM" [gbyte*hour]
            # gpu
            add_usage("dn20ml8ifdps6m7048an", gpus * instance_num, resource_name, resource_type) # Intel Ice Lake with Nvidia T4. GPU [gpus*hour]

    if(platform_id == "standard-v3-t4i"):
        # preemptible
        if(preemptible == True):
            # cpu
            add_usage("dn2960mi7268n67o8iae", cores * instance_num, resource_name, resource_type) # Intel Ice lake with t4i. 100% vCPU - preemptible instances [core*hour]
            # ram
            add_usage("dn25rffeums4j1ku5649", memory * instance_num, resource_name, resource_type) # Intel Ice lake with t4i. RAM - preemptible instances [gbyte*hour]
            # gpu
            add_usage("dn2qlml2u48bng4jgilh", gpus * instance_num, resource_name, resource_type) # Intel Ice lake with t4i. GPU - preemptible instances [gpus*hour]
            
        # non preemptible
        if(preemptible == False):
            # cpu
            add_usage("dn242l2ivnhdd5so2oga", cores * instance_num, resource_name, resource_type) # Intel Ice lake with t4i. 100% vCPU [core*hour]
            # ram
            add_usage("dn290pbmohupnus9ajb7", memory * instance_num, resource_name, resource_type) # Intel Ice lake with t4i. RAM [gbyte*hour]
            # gpu
            add_usage("dn2hql9evci880d8jq7i", gpus * instance_num, resource_name, resource_type) # Intel Ice lake with t4i. GPU" [gpus*hour]

    if(platform_id == "gpu-standard-v3"):
        # preemptible
        if(preemptible == True):
            # cpu
            add_usage("dn2tvs05nnrib706hgnt", cores * instance_num, resource_name, resource_type) # AMD Epyc with Nvidia A100. 100% vCPU - preemptible instances [core*hour]
            # ram
            add_usage("dn2m4gusa7m7t4hl6vo2", memory * instance_num, resource_name, resource_type) # AMD Epyc with Nvidia A100. RAM \u2014 preemptible instances [gbyte*hour]
            # gpu
            add_usage("dn211dses9ju3abvq0bs", gpus * instance_num, resource_name, resource_type) # AMD Epyc with Nvidia A100. GPU - preemptible instances [gpus*hour]
            
        # non preemptible
        if(preemptible == False): 
            # cpu
            add_usage("dn28c1erut6m9f9uem08", cores * instance_num, resource_name, resource_type) # AMD Epyc with Nvidia A100. 100% vCPU [core*hour]
            # ram
            add_usage("dn21jcm82510bfa6is22", memory * instance_num, resource_name, resource_type) # AMD Epyc with Nvidia A100. RAM [gbyte*hour]
            # gpu
            add_usage("dn2395q10bihjmm2b0v6", gpus * instance_num, resource_name, resource_type) # AMD Epyc with Nvidia A100. GPU [gpus*hour]

    if(platform_id == "gpu-standard-v3i"):
        # preemptible
        if(preemptible == True):
            # cpu
            add_usage("dn2o9fiqemifmch1dq7c", cores * instance_num, resource_name, resource_type) # AMD Epyc 9474F with Gen2. 100% vCPU - preemptible instances [core*hour]
            # ram
            add_usage("dn2mgiub24223fh5mvgv", memory * instance_num, resource_name, resource_type) # AMD Epyc 9474F with Gen2. RAM - preemptible instances [gbyte*hour]
            # gpu
            add_usage("dn2qvcfe8i5vqlrvterc", gpus * instance_num, resource_name, resource_type) # AMD Epyc 9474F with Gen2. GPU - preemptible instances [gpus*hour]
            
        # non preemptible
        if(preemptible == False): 
            # cpu
            add_usage("dn2fd3g50rub98vfprlt", cores * instance_num, resource_name, resource_type) # AMD Epyc 9474F with Gen2. 100% vCPU [core*hour]
            # ram
            add_usage("dn2h5gi2u2l3bdclrput", memory * instance_num, resource_name, resource_type) # AMD Epyc 9474F with Gen2. RAM [gbyte*hour]
            # gpu
            add_usage("dn2jfrjoic5h3nh7e6jh", gpus * instance_num, resource_name, resource_type) # AMD Epyc 9474F with Gen2. GPU [gpus*hour]

    if(platform_id == "gpu-standard-v2"):
        # preemptible
        if(preemptible == True):
            # cpu
            add_usage("dn2h4u30djq3jhh8dqh8", cores * instance_num, resource_name, resource_type) # Intel Cascade Lake with Nvidia Tesla v100. 100% vCPU - preemptible instances [core*hour]
            # ram
            add_usage("dn2hotj7skno0turhbq1", memory * instance_num, resource_name, resource_type) # Intel Cascade Lake with Nvidia Tesla v100. RAM \u2014 preemptible instances [gbyte*hour]
            # gpu
            add_usage("dn23ppvthcls7rjt5pol", gpus * instance_num, resource_name, resource_type) # Intel Cascade Lake with Nvidia Tesla v100. GPU - preemptible instances [gpus*hour]
            
        # non preemptible
        if(preemptible == False):
            # cpu
            add_usage("dn2udmu2aa9jm5a8f4ug", cores * instance_num, resource_name, resource_type) # Intel Cascade Lake with Nvidia Tesla v100. 100% vCPU [core*hour]
            # ram
            add_usage("dn2qtp90p3r8l8vakmm6", memory * instance_num, resource_name, resource_type) # Intel Cascade Lake with Nvidia Tesla v100. RAM [gbyte*hour]
            # gpu
            add_usage("dn2dlvuk2ecf6hu0kjtl", gpus * instance_num, resource_name, resource_type) # Intel Cascade Lake with Nvidia Tesla v100. GPU [gpus*hour]

    if(platform_id == "gpu-standard-v1"):
        # preemptible
        if(preemptible == True):
            # cpu
            add_usage("dn2t7aa68lehsmvo5mss", cores * instance_num, resource_name, resource_type) # Intel Broadwell with Nvidia Tesla v100. 100% vCPU - preemptible instances [core*hour]
            # ram
            add_usage("dn2k0omvmglh857u60vu", memory * instance_num, resource_name, resource_type) # Intel Broadwell with Nvidia Tesla v100. RAM - preemptible instances [gbyte*hour]
            # gpu
            add_usage("dn2lov15qqamcimfv84q", gpus * instance_num, resource_name, resource_type) # Intel Broadwell with Nvidia Tesla v100. GPU - preemptible instances [gpus*hour]
            
        # non preemptible
        if(preemptible == False):
            # cpu
            add_usage("dn2sfcnkn3jlhmq568ac", cores * instance_num, resource_name, resource_type) # Intel Broadwell with Nvidia Tesla v100. 100% vCPU [core*hour]
            # ram
            add_usage("dn2nccae8nra81iqphdn", memory * instance_num, resource_name, resource_type) # Intel Broadwell with Nvidia Tesla v100. RAM [gbyte*hour]
            # gpu
            add_usage("dn2oroscvvtb6sqtt83i", gpus * instance_num, resource_name, resource_type) # Intel Broadwell with Nvidia Tesla v100. GPU [gpus*hour]
    
    if(boot_disk_size > 0):
        if(boot_disk_type == "network-hdd"):
            add_usage("dn2al287u6jr3a710u8g", boot_disk_size * instance_num, resource_name, resource_type) # Standard network storage (HDD) [gbyte*hour]
        if(boot_disk_type == "network-ssd"):
            add_usage("dn27ajm6m8mnfcshbi61", boot_disk_size * instance_num, resource_name, resource_type) # Fast network storage (SSD) [gbyte*hour]
        if(boot_disk_type == "network-ssd-nonreplicated"):
            add_usage("dn24kdllggk8ahsol15g", boot_disk_size * instance_num, resource_name, resource_type) # Non-replicated fast network storage (SSD) [gbyte*hour]
        if(boot_disk_type == "network-ssd-io-m3"):
            add_usage("dn25ksor7p112bvs2qts", boot_disk_size * instance_num, resource_name, resource_type) # Ultra fast network storage with 3 replicas (SSD) [gbyte*hour]

    if(network_nat):
        add_usage("dn229q5mnmp58t58tfel", instance_num, resource_name, resource_type) # Public IP address [fip*hour]

    logging.debug(json.dumps(resource_values, indent=4).replace('\n', '\r'))
    return 0

# yandex_compute_filesystem
def process_filesystem(resource):
    resource_type       = resource["type"]
    resource_name       = resource["name"]
    resource_values     = resource["values"]

    disk_size           = resource_values.get("size", 0)
    disk_type           = resource_values.get("type", "network-hdd")

    if(disk_size > 0):
        if(disk_type == "network-hdd"):
            add_usage("dn2al287u6jr3a710u8g", disk_size, resource_name, resource_type) # Standard network storage (HDD) [gbyte*hour]
        if(disk_type == "network-ssd"):
            add_usage("dn27ajm6m8mnfcshbi61", disk_size, resource_name, resource_type) # Fast network storage (SSD) [gbyte*hour]

    logging.debug(json.dumps(resource_values, indent=4).replace('\n', '\r'))
    return 0

# yandex_kubernetes_cluster
def process_kube_cluster(resource):
    resource_type       = resource["type"]
    resource_name       = resource["name"]
    resource_values     = resource["values"]

    for master in resource_values.get("master", []):
        if "zonal" in master:
            add_usage("dn2tdli7u18tvvc28ov8", 1, resource_name, resource_type) # Managed Kubernetes. Zonal Master - small (hour)
        elif "regional" in master:
            add_usage("dn2j2khrfcdc4p1aki30", 1, resource_name, resource_type) # Managed Kubernetes. Regional Master - small (hour)

    logging.debug(json.dumps(resource_values, indent=4).replace('\n', '\r'))
    return 0

# yandex_kubernetes_node_group
def process_kube_node(resource):
    resource_type       = resource["type"]
    resource_name       = resource["name"]
    resource_values     = resource["values"]

    auto_scale          = resource_values["scale_policy"][0].get("auto_scale", [])
    fixed_scale         = resource_values["scale_policy"][0].get("fixed_scale", [])
    boot_disk_size      = resource_values["instance_template"][0]["boot_disk"][0].get("size", 0)
    boot_disk_type      = resource_values["instance_template"][0]["boot_disk"][0].get("type", "network-hdd")
    network_nat         = resource_values["instance_template"][0]["network_interface"][0].get("nat", False) # проверить несколько интерфейсов
    platform_id         = resource_values["instance_template"][0]["platform_id"]
    resources_cores     = resource_values["instance_template"][0]["resources"][0]["cores"]
    resources_fraction  = resource_values["instance_template"][0]["resources"][0].get("core_fraction", 100)
    resources_memory    = resource_values["instance_template"][0]["resources"][0]["memory"]
    resources_gpus      = resource_values["instance_template"][0]["resources"][0]["gpus"]
    scheduling_policy   = resource_values["instance_template"][0].get("scheduling_policy", [{}])
    preemptible         = scheduling_policy[0].get("preemptible", False)

    if auto_scale:
        instance_num = auto_scale[0]["initial"]
    elif fixed_scale:
        instance_num = fixed_scale[0]["size"]

    if(platform_id == "standard-v3"):
        # preemptible
        if(preemptible == True):
            # cpu
            if(resources_fraction == 100):
                add_usage("dn2e2fphfupugm21k4hv", resources_cores*instance_num, resource_name, resource_type) # Intel Ice Lake. 100% vCPU \u2014 preemptible instances [core*hour]
            if(resources_fraction == 50):
                add_usage("dn2333h2iv190t06bon8", resources_cores*instance_num, resource_name, resource_type) # Intel Ice Lake. 50% vCPU \u2014 preemptible instances [core*hour]
            if(resources_fraction == 20):
                add_usage("dn2pdedm5fon78kbl0fh", resources_cores*instance_num, resource_name, resource_type) # Intel Ice Lake. 20% vCPU \u2014 preemptible instances [core*hour]
            # ram
            add_usage("dn26ur5frjbgdek2a0g5", resources_memory*instance_num, resource_name, resource_type) # Intel Ice Lake. RAM \u2014 preemptible instances [gbyte*hour]
            
        # non preemptible
        if(preemptible == False):
            # cpu
            if(resources_fraction == 100):
                add_usage("dn2k3vqlk9snp1jv351u", resources_cores*instance_num, resource_name, resource_type) # Intel Ice Lake. 100% vCPU [core*hour]
            if(resources_fraction == 50):
                add_usage("dn2f0q0d6gtpcom4b1p6", resources_cores*instance_num, resource_name, resource_type) # Intel Ice Lake. 50% vCPU [core*hour]
            if(resources_fraction == 20):
                add_usage("dn2r8aklo79bmpkd87l3", resources_cores*instance_num, resource_name, resource_type) # Intel Ice Lake. 20% vCPU [core*hour]
            # ram
            add_usage("dn2ilq72mjc3bej6j74p", resources_memory*instance_num, resource_name, resource_type) # Intel Ice Lake. RAM [gbyte*hour]

    if(platform_id == "standard-v2"):
        # preemptible
        if(preemptible == True):
            # cpu
            if(resources_fraction == 100):
                add_usage("dn2ipnaa10sls6i7osfv", resources_cores*instance_num, resource_name, resource_type) # Intel Cascade Lake. 100% vCPU \u2014 preemptible instances [core*hour]
            if(resources_fraction == 50):
                add_usage("dn20jng1b3a6ggtn52bo", resources_cores*instance_num, resource_name, resource_type) # Intel Cascade Lake. 50% vCPU \u2014 preemptible instances [core*hour]
            if(resources_fraction == 20):
                add_usage("dn2krclp8uj3432vmpre", resources_cores*instance_num, resource_name, resource_type) # Intel Cascade Lake. 20% vCPU \u2014 preemptible instances [core*hour]
            if(resources_fraction == 5):
                add_usage("dn292ebti5dcjio7vh2s", resources_cores*instance_num, resource_name, resource_type) # Intel Cascade Lake. 5% vCPU \u2014 preemptible instances [core*hour]
            # ram
            add_usage("dn26ur5frjbgdek2a0g5", resources_memory*instance_num, resource_name, resource_type) # Intel Ice Lake. RAM \u2014 preemptible instances [gbyte*hour]
            
        # non preemptible
        if(preemptible == False):
            # cpu
            if(resources_fraction == 100):
                add_usage("dn218a07u143r9v1r5ms", resources_cores*instance_num, resource_name, resource_type) # Intel Cascade Lake. 100% vCPU [core*hour]
            if(resources_fraction == 50):
                add_usage("dn2qbqi1am9oq6oc9s05", resources_cores*instance_num, resource_name, resource_type) # Intel Cascade Lake. 50% vCPU [core*hour]
            if(resources_fraction == 20):
                add_usage("dn26skitjdon841jqit7", resources_cores*instance_num, resource_name, resource_type) # Intel Cascade Lake. 20% vCPU [core*hour]
            if(resources_fraction == 5):
                add_usage("dn2l09d8brnv9s8m5p2r", resources_cores*instance_num, resource_name, resource_type) # Intel Cascade Lake. 5% vCPU [core*hour]
            # ram
            add_usage("dn2fhtcoocq50j1uj4tg", resources_memory*instance_num, resource_name, resource_type) # Intel Cascade Lake. RAM [gbyte*hour]
    
    if(platform_id == "standard-v1"):
        # preemptible
        if(preemptible == True):
            # cpu
            if(resources_fraction == 100):
                add_usage("dn247qigcq66fq6t3tk5", resources_cores*instance_num, resource_name, resource_type) # Intel Broadwell. 100% vCPU \u2014 preemptible instances [core*hour]
            if(resources_fraction == 20):
                add_usage("dn24sf8vh5cvj53voa7k", resources_cores*instance_num, resource_name, resource_type) # Intel Broadwell. 20% vCPU \u2014 preemptible instances [core*hour]
            if(resources_fraction == 5):
                add_usage("dn2g5qo1211n5k8i1s3v", resources_cores*instance_num, resource_name, resource_type) # Intel Broadwell. 5% vCPU \u2014 preemptible instances [core*hour]
            # ram
            add_usage("dn2u497ok1kl70on0ta2", resources_memory*instance_num, resource_name, resource_type) # Intel Broadwell. RAM \u2014 preemptible instances [gbyte*hour]
            
        # non preemptible
        if(preemptible == False):
            # cpu
            if(resources_fraction == 100):
                add_usage("dn299ll54t5jt2gojh7e", resources_cores*instance_num, resource_name, resource_type) # Intel Broadwell. 100% vCPU [core*hour]
            if(resources_fraction == 20):
                add_usage("dn2vmq6na03r9vlds7j8", resources_cores*instance_num, resource_name, resource_type) # Intel Broadwell. 20% vCPU [core*hour]
            if(resources_fraction == 5):
                add_usage("dn2pm2gap1cc09a33s06", resources_cores*instance_num, resource_name, resource_type) # Intel Broadwell. 5% vCPU [core*hour]
            # ram
            add_usage("dn2dka206olokggsieuu", resources_memory*instance_num, resource_name, resource_type) # Intel Broadwell. RAM [gbyte*hour]
    
    if(platform_id == "highfreq-v3"): #! нет данных в биллинг апи
        # cpu
        add_usage("xxx", resources_cores*instance_num, resource_name, resource_type) # Intel Ice Lake (Compute Optimized). 100% vCPU [core*hour]
        # ram
        add_usage("xxx", resources_memory*instance_num, resource_name, resource_type) # Intel Ice Lake (Compute Optimized). RAM [gbyte*hour]

    if(platform_id == "standard-v3-t4"):
        # preemptible
        if(preemptible == True):
            # cpu
            add_usage("dn2lsfskfirek2985fnd", resources_cores*instance_num, resource_name, resource_type) # Intel Ice Lake with Nvidia T4. 100% vCPU \u2014 preemptible instances [core*hour]
            # ram
            add_usage("dn2im0g43iedeohe4sac", resources_memory*instance_num, resource_name, resource_type) # Intel Ice Lake with Nvidia T4. RAM - preemptible instances [gbyte*hour]
            # gpu
            add_usage("dn2cpk4mc82b1vib72e5", resources_gpus*instance_num, resource_name, resource_type) # Intel Ice Lake with Nvidia T4. GPU - preemptible instances [gpus*hour]
            
        # non preemptible
        if(preemptible == False):
            # cpu
            add_usage("dn24b7m6qol7tb7tukga", resources_cores*instance_num, resource_name, resource_type) # Intel Ice Lake with Nvidia T4. 100% vCPU [core*hour]
            # ram
            add_usage("dn2lg2hrvbn5b8lm7em4", resources_memory*instance_num, resource_name, resource_type) # Intel Ice Lake with Nvidia T4. RAM" [gbyte*hour]
            # gpu
            add_usage("dn20ml8ifdps6m7048an", resources_gpus*instance_num, resource_name, resource_type) # Intel Ice Lake with Nvidia T4. GPU [gpus*hour]
    
    if(platform_id == "standard-v3-t4i"):
        # preemptible
        if(preemptible == True):
            # cpu
            add_usage("dn2960mi7268n67o8iae", resources_cores*instance_num, resource_name, resource_type) # Intel Ice lake with t4i. 100% vCPU - preemptible instances [core*hour]
            # ram
            add_usage("dn25rffeums4j1ku5649", resources_memory*instance_num, resource_name, resource_type) # Intel Ice lake with t4i. RAM - preemptible instances [gbyte*hour]
            # gpu
            add_usage("dn2qlml2u48bng4jgilh", resources_gpus*instance_num, resource_name, resource_type) # Intel Ice lake with t4i. GPU - preemptible instances [gpus*hour]
            
        # non preemptible
        if(preemptible == False):
            # cpu
            add_usage("dn242l2ivnhdd5so2oga", resources_cores*instance_num, resource_name, resource_type) # Intel Ice lake with t4i. 100% vCPU [core*hour]
            # ram
            add_usage("dn290pbmohupnus9ajb7", resources_memory*instance_num, resource_name, resource_type) # Intel Ice lake with t4i. RAM [gbyte*hour]
            # gpu
            add_usage("dn2hql9evci880d8jq7i", resources_gpus*instance_num, resource_name, resource_type) # Intel Ice lake with t4i. GPU" [gpus*hour]

    if(platform_id == "gpu-standard-v3"):
        # preemptible
        if(preemptible == True):
            # cpu
            add_usage("dn2tvs05nnrib706hgnt", resources_cores*instance_num, resource_name, resource_type) # AMD Epyc with Nvidia A100. 100% vCPU - preemptible instances [core*hour]
            # ram
            add_usage("dn2m4gusa7m7t4hl6vo2", resources_memory*instance_num, resource_name, resource_type) # AMD Epyc with Nvidia A100. RAM \u2014 preemptible instances [gbyte*hour]
            # gpu
            add_usage("dn211dses9ju3abvq0bs", resources_gpus*instance_num, resource_name, resource_type) # AMD Epyc with Nvidia A100. GPU - preemptible instances [gpus*hour]
            
        # non preemptible
        if(preemptible == False): 
            # cpu
            add_usage("dn28c1erut6m9f9uem08", resources_cores*instance_num, resource_name, resource_type) # AMD Epyc with Nvidia A100. 100% vCPU [core*hour]
            # ram
            add_usage("dn21jcm82510bfa6is22", resources_memory*instance_num, resource_name, resource_type) # AMD Epyc with Nvidia A100. RAM [gbyte*hour]
            # gpu
            add_usage("dn2395q10bihjmm2b0v6", resources_gpus*instance_num, resource_name, resource_type) # AMD Epyc with Nvidia A100. GPU [gpus*hour]

    if(platform_id == "gpu-standard-v3i"):
        # preemptible
        if(preemptible == True):
            # cpu
            add_usage("dn2o9fiqemifmch1dq7c", resources_cores*instance_num, resource_name, resource_type) # AMD Epyc 9474F with Gen2. 100% vCPU - preemptible instances [core*hour]
            # ram
            add_usage("dn2mgiub24223fh5mvgv", resources_memory*instance_num, resource_name, resource_type) # AMD Epyc 9474F with Gen2. RAM - preemptible instances [gbyte*hour]
            # gpu
            add_usage("dn2qvcfe8i5vqlrvterc", resources_gpus*instance_num, resource_name, resource_type) # AMD Epyc 9474F with Gen2. GPU - preemptible instances [gpus*hour]
            
        # non preemptible
        if(preemptible == False): 
            # cpu
            add_usage("dn2fd3g50rub98vfprlt", resources_cores*instance_num, resource_name, resource_type) # AMD Epyc 9474F with Gen2. 100% vCPU [core*hour]
            # ram
            add_usage("dn2h5gi2u2l3bdclrput", resources_memory*instance_num, resource_name, resource_type) # AMD Epyc 9474F with Gen2. RAM [gbyte*hour]
            # gpu
            add_usage("dn2jfrjoic5h3nh7e6jh", resources_gpus*instance_num, resource_name, resource_type) # AMD Epyc 9474F with Gen2. GPU [gpus*hour]

    if(platform_id == "gpu-standard-v2"):
        # preemptible
        if(preemptible == True):
            # cpu
            add_usage("dn2h4u30djq3jhh8dqh8", resources_cores*instance_num, resource_name, resource_type) # Intel Cascade Lake with Nvidia Tesla v100. 100% vCPU - preemptible instances [core*hour]
            # ram
            add_usage("dn2hotj7skno0turhbq1", resources_memory*instance_num, resource_name, resource_type) # Intel Cascade Lake with Nvidia Tesla v100. RAM \u2014 preemptible instances [gbyte*hour]
            # gpu
            add_usage("dn23ppvthcls7rjt5pol", resources_gpus*instance_num, resource_name, resource_type) # Intel Cascade Lake with Nvidia Tesla v100. GPU - preemptible instances [gpus*hour]
            
        # non preemptible
        if(preemptible == False):
            # cpu
            add_usage("dn2udmu2aa9jm5a8f4ug", resources_cores*instance_num, resource_name, resource_type) # Intel Cascade Lake with Nvidia Tesla v100. 100% vCPU [core*hour]
            # ram
            add_usage("dn2qtp90p3r8l8vakmm6", resources_memory*instance_num, resource_name, resource_type) # Intel Cascade Lake with Nvidia Tesla v100. RAM [gbyte*hour]
            # gpu
            add_usage("dn2dlvuk2ecf6hu0kjtl", resources_gpus*instance_num, resource_name, resource_type) # Intel Cascade Lake with Nvidia Tesla v100. GPU [gpus*hour]

    if(platform_id == "gpu-standard-v1"):
        # preemptible
        if(preemptible == True):
            # cpu
            add_usage("dn2t7aa68lehsmvo5mss", resources_cores*instance_num, resource_name, resource_type) # Intel Broadwell with Nvidia Tesla v100. 100% vCPU - preemptible instances [core*hour]
            # ram
            add_usage("dn2k0omvmglh857u60vu", resources_memory*instance_num, resource_name, resource_type) # Intel Broadwell with Nvidia Tesla v100. RAM - preemptible instances [gbyte*hour]
            # gpu
            add_usage("dn2lov15qqamcimfv84q", resources_gpus*instance_num, resource_name, resource_type) # Intel Broadwell with Nvidia Tesla v100. GPU - preemptible instances [gpus*hour]
            
        # non preemptible
        if(preemptible == False):
            # cpu
            add_usage("dn2sfcnkn3jlhmq568ac", resources_cores*instance_num, resource_name, resource_type) # Intel Broadwell with Nvidia Tesla v100. 100% vCPU [core*hour]
            # ram
            add_usage("dn2nccae8nra81iqphdn", resources_memory*instance_num, resource_name, resource_type) # Intel Broadwell with Nvidia Tesla v100. RAM [gbyte*hour]
            # gpu
            add_usage("dn2oroscvvtb6sqtt83i", resources_gpus*instance_num, resource_name, resource_type) # Intel Broadwell with Nvidia Tesla v100. GPU [gpus*hour]
    
    if(boot_disk_size > 0):
        if(boot_disk_type == "network-ssd"):
            add_usage("dn27ajm6m8mnfcshbi61", boot_disk_size * instance_num, resource_name, resource_type) # Fast network storage (SSD) [gbyte*hour]
        if(boot_disk_type == "network-hdd"):
            add_usage("dn2al287u6jr3a710u8g", boot_disk_size * instance_num, resource_name, resource_type) # Standard network storage (HDD) [gbyte*hour]
        if(boot_disk_type == "network-ssd-nonreplicated"):
            add_usage("dn24kdllggk8ahsol15g", boot_disk_size * instance_num, resource_name, resource_type) # Non-replicated fast network storage (SSD) [gbyte*hour]
        if(boot_disk_type == "network-ssd-io-m3"):
            add_usage("dn25ksor7p112bvs2qts", boot_disk_size * instance_num, resource_name, resource_type) # Ultra fast network storage with 3 replicas (SSD) [gbyte*hour]

    if(network_nat):
        add_usage("dn229q5mnmp58t58tfel", instance_num, resource_name, resource_type) # Public IP address [fip*hour]

    logging.debug(json.dumps(resource_values, indent=4).replace('\n', '\r'))
    return 0

# yandex_mdb_mysql_cluster
def process_mdb_mysql(resource):
    resource_type       = resource["type"]
    resource_name       = resource["name"]
    resource_values     = resource["values"]

    disk_size           = resource_values["resources"][0].get("disk_size", 0)
    disk_type           = resource_values["resources"][0].get("disk_type_id", "network-hdd")
    preset_id           = resource_values["resources"][0].get("resource_preset_id", [])
    instances           = resource_values.get("host", [])

    try:
        cores, core_fraction, memory, platform_id = get_mdb_preset('mysql', preset_id)
    except ValueError as e:
        logging.error(e)

    instance_num        = len(instances)
    public_ip_num       = sum(1 for instance in instances if instance.get("assign_public_ip") is True)

    if(platform_id == "standard-v3"):
        # cpu
        if(core_fraction == 100):
            add_usage("dn2mfa1c935rjc6t4eek", cores * instance_num, resource_name, resource_type) # MySQL. Intel Ice Lake. 100% vCPU [core*hour]
        if(core_fraction == 50):
            add_usage("dn2lo0l3birckqii0kpd", cores * instance_num, resource_name, resource_type) # MySQL. Intel Ice Lake. 50% vCPU [core*hour]
        # ram
        add_usage("dn2nhjlpvll7kron0lv0", memory * instance_num, resource_name, resource_type) # MySQL. Intel Ice Lake. RAM [gbyte*hour]

    if(platform_id == "highfreq-v3"): #! нет в биллинге
        #! MySQL. Intel Ice Lake (Compute Optimized). Software accelerated network
        # cpu
        add_usage("dn26hjuqup86h8g2dc4o", cores * instance_num, resource_name, resource_type) # MySQL. Intel Ice Lake (Compute Optimised). 100% vCPU [core*hour]
        # ram
        add_usage("dn2afr14vhrtu5rgvtvj", memory * instance_num, resource_name, resource_type) # MySQL. Intel Ice Lake (Compute Optimized). RAM [gbyte*hour]
    
    if(platform_id == "standard-v2"):
        # cpu
        if(core_fraction == 100):
            add_usage("dn2ekqj88rk6cj186bgv", cores * instance_num, resource_name, resource_type) # MySQL. Intel Cascade Lake. 100% vCPU [core*hour]
        if(core_fraction == 50):
            add_usage("dn23em5ur8pmc5oe1ugg", cores * instance_num, resource_name, resource_type) # MySQL. Intel Cascade Lake. 50% vCPU [core*hour]
        if(core_fraction == 20):
            add_usage("dn29qcell9096oecia43", cores * instance_num, resource_name, resource_type) # MySQL. Intel Cascade Lake. 20% vCPU [core*hour]
        if(core_fraction == 5):
            add_usage("dn2ikmrgbcfqnq0e89rh", cores * instance_num, resource_name, resource_type) # MySQL. Intel Cascade Lake. 5% vCPU [core*hour]
        # ram
        add_usage("dn2q9cgq04cl6ju1j2k7", memory * instance_num, resource_name, resource_type) # MySQL. Intel Cascade Lake. RAM [gbyte*hour]
    
    if(platform_id == "standard-v1"):
        # cpu
        if(core_fraction == 100):
            add_usage("dn2hi38l2amv53lnkudh", cores * instance_num, resource_name, resource_type) # MySQL. Intel Broadwell. 100% vCPU [core*hour]
        if(core_fraction == 50):
            add_usage("dn234519saji1v5gtbk7", cores * instance_num, resource_name, resource_type) # MySQL. Intel Broadwell. 50% vCPU [core*hour]
        if(core_fraction == 20):
            add_usage("dn24fhsc8h68f51o549s", cores * instance_num, resource_name, resource_type) # MySQL. Intel Broadwell. 20% vCPU [core*hour]
        if(core_fraction == 5):
            add_usage("dn2manmpat7cv2ge9kbm", cores * instance_num, resource_name, resource_type) # MySQL. Intel Broadwell. 5% vCPU [core*hour]
        # ram
        add_usage("dn2s8tj0qdakj5c49e5o", memory * instance_num, resource_name, resource_type) # MySQL. Intel Broadwell. RAM [gbyte*hour]

    if(public_ip_num > 0):
        add_usage("dn2non93sh0grnlrjb7m", public_ip_num, resource_name, resource_type) # Public IP address - MySQL [fip*hour]

    if(disk_type == "network-ssd"):
        add_usage("dn2j7e6hs2j2ugni50lq", disk_size * instance_num, resource_name, resource_type) # Fast network storage \u2014 MySQL [gbyte*hour]
    if(disk_type == "network-hdd"):
        add_usage("dn2thbds4400ckbijvch", disk_size * instance_num, resource_name, resource_type) # Standard network storage \u2014 MySQL [gbyte*hour]
    if(disk_type == "network-ssd-nonreplicated"):
        add_usage("dn286bla0e9c7d2fnqst", disk_size * instance_num, resource_name, resource_type) # Non-replicated fast network storage \u2014 MySQL [gbyte*hour]
    if(disk_type == "network-ssd-io-m3"):
        add_usage("dn2po189eb088u6kpa9o", disk_size * instance_num, resource_name, resource_type) # Ultra fast network storage with 3 replicas (SSD) \u2014 MySQL [gbyte*hour]
    if(disk_type == "local-ssd"):
        add_usage("dn28goa6h2rkk2skokee", disk_size * instance_num, resource_name, resource_type) # Fast local storage \u2014 MySQL [gbyte*hour]

    logging.debug(json.dumps(resource_values, indent=4).replace('\n', '\r'))
    return 0

# yandex_mdb_postgresql_cluster
def process_mdb_postgre(resource):
    resource_type       = resource["type"]
    resource_name       = resource["name"]
    resource_values     = resource["values"]

    disk_size           = resource_values["config"][0]["resources"][0].get("disk_size", 0)
    disk_type           = resource_values["config"][0]["resources"][0].get("disk_type_id", "network-hdd")
    preset_id           = resource_values["config"][0]["resources"][0].get("resource_preset_id", [])
    instances           = resource_values.get("host", [])

    try:
        cores, core_fraction, memory, platform_id = get_mdb_preset('postgresql', preset_id)
    except ValueError as e:
        logging.error(e)

    instance_num        = len(instances)
    public_ip_num       = sum(1 for instance in instances if instance.get("assign_public_ip") is True)

    if(platform_id == "standard-v3"):
        # cpu
        if(core_fraction == 100):
            add_usage("dn232gunmdllqdl5cicd", cores * instance_num, resource_name, resource_type) # PostgreSQL. Intel Ice Lake. 100% vCPU [core*hour]
        if(core_fraction == 50):
            add_usage("dn20phj76ak2oh3m4sgn", cores * instance_num, resource_name, resource_type) # PostgreSQL. Intel Ice Lake. 50% vCPU [core*hour]
        # ram
        add_usage("dn2snd5f5rifj49dhovh", memory * instance_num, resource_name, resource_type) # PostgreSQL. Intel Ice Lake. RAM [gbyte*hour]

    #! добавить highfreq платформу
    if(platform_id == "highfreq-v3"):
        #! PostgreSQL. Intel Ice Lake (Compute Optimized). Software accelerated network
        # cpu
        add_usage("dn2878t3j92nm7ht5tlq", cores * instance_num, resource_name, resource_type) # PostgreSQL. Intel Ice Lake (Compute Optimised). 100% vCPU [core*hour]
        # ram
        add_usage("dn2dflbiele6g9he24ee", memory * instance_num, resource_name, resource_type) # PostgreSQL. Intel Ice Lake (Compute Optimized). RAM [gbyte*hour]

    if(platform_id == "standard-v2"):
        # cpu
        if(core_fraction == 100):
            add_usage("dn2foiqm6aoaghmjcr38", cores * instance_num, resource_name, resource_type) # PostgreSQL. Intel Cascade Lake. 100% vCPU [core*hour]
        if(core_fraction == 50):
            add_usage("dn2ac5geuj2i95lkh5te", cores * instance_num, resource_name, resource_type) # PostgreSQL. Intel Cascade Lake. 50% vCPU [core*hour]
        if(core_fraction == 20):
            add_usage("dn2k4nll5o0unlnnn0hf", cores * instance_num, resource_name, resource_type) # PostgreSQL. Intel Cascade Lake. 20% vCPU [core*hour]
        if(core_fraction == 5):
            add_usage("dn217kngosua0ige7glr", cores * instance_num, resource_name, resource_type) # PostgreSQL. Intel Cascade Lake. 5% vCPU [core*hour]
        # ram
        add_usage("dn2b1ve4tifofkbpqtlo", memory * instance_num, resource_name, resource_type) # PostgreSQL. Intel Cascade Lake. RAM [gbyte*hour]
    
    if(platform_id == "standard-v1"):
        # cpu
        if(core_fraction == 100):
            add_usage("dn2n5qctucuvrif2l6v2", cores * instance_num, resource_name, resource_type) # PostgreSQL. Intel Broadwell. 100% vCPU [core*hour]
        if(core_fraction == 50):
            add_usage("dn24saqltp4lsu0kgc6a", cores * instance_num, resource_name, resource_type) # PostgreSQL. Intel Broadwell. 50% vCPU [core*hour]
        if(core_fraction == 20):
            add_usage("dn24heoov30dnk16kvqi", cores * instance_num, resource_name, resource_type) # PostgreSQL. Intel Broadwell. 20% vCPU [core*hour]
        if(core_fraction == 5):
            add_usage("dn26tqk6cr5ocu7v3j5i", cores * instance_num, resource_name, resource_type) # PostgreSQL. Intel Broadwell. 5% vCPU [core*hour]
        # ram
        add_usage("dn2i2qka7e75bh6ok7he", memory * instance_num, resource_name, resource_type) # PostgreSQL. Intel Broadwell. RAM [gbyte*hour]

    if(public_ip_num > 0):
        add_usage("dn2cc943s27vr5gviq0k", public_ip_num, resource_name, resource_type) # Public IP address - PostgreSQL [fip*hour]

    if(disk_type == "network-ssd"):
        add_usage("dn2euvjs01kht9oftfji", disk_size * instance_num, resource_name, resource_type) # Fast network storage \u2014 PostgreSQL [gbyte*hour]
    if(disk_type == "network-hdd"):
        add_usage("dn2l0lh2aon42b2d7jb9", disk_size * instance_num, resource_name, resource_type) # Standard network storage \u2014 PostgreSQL [gbyte*hour]
    if(disk_type == "network-ssd-nonreplicated"):
        add_usage("dn2t1rhogdm8t0gtao1s", disk_size * instance_num, resource_name, resource_type) # Non-replicated fast network storage \u2014 PostgreSQL [gbyte*hour]
    if(disk_type == "network-ssd-io-m3"):
        add_usage("dn2vi9oeraem9ptu27ad", disk_size * instance_num, resource_name, resource_type) # Ultra fast network storage with 3 replicas (SSD) \u2014 PostgreSQL [gbyte*hour]
    if(disk_type == "local-ssd"):
        add_usage("dn2nr78ch39birtq8cud", disk_size * instance_num, resource_name, resource_type) # Fast local storage \u2014 PostgreSQL [gbyte*hour]

    logging.debug(json.dumps(resource_values, indent=4).replace('\n', '\r'))
    return 0

# yandex_mdb_clickhouse_cluster
def process_mdb_clickhouse(resource):
    resource_type       = resource["type"]
    resource_name       = resource["name"]
    resource_values     = resource["values"]

    disk_size_ch           = resource_values["clickhouse"][0]["resources"][0].get("disk_size", 0)
    disk_type_ch           = resource_values["clickhouse"][0]["resources"][0].get("disk_type_id", "network-hdd")
    preset_id_ch           = resource_values["clickhouse"][0]["resources"][0].get("resource_preset_id", [])

    disk_size_zk           = resource_values["zookeeper"][0]["resources"][0].get("disk_size", 0)
    disk_type_zk           = resource_values["zookeeper"][0]["resources"][0].get("disk_type_id", "network-hdd")
    preset_id_zk           = resource_values["zookeeper"][0]["resources"][0].get("resource_preset_id", [])
    
    instances              = resource_values.get("host", [])

    try:
        cores, core_fraction, memory, platform_id = get_mdb_preset('clickhouse', preset_id_ch)
    except ValueError as e:
        logging.error(e)

    try:
        cores_zk, core_fraction_zk, memory_zk, platform_id_zk = get_mdb_preset('clickhouse', preset_id_zk)
    except ValueError as e:
        logging.error(e)

    instances_num_ch        = sum(1 for instance in instances if instance['type'] == 'CLICKHOUSE')
    instances_num_zk        = sum(1 for instance in instances if instance['type'] == 'ZOOKEEPER')
    public_ip_num_ch        = sum(1 for instance in instances if (instance.get("assign_public_ip") is True and instance['type'] == 'CLICKHOUSE'))

    # Clickhouse
    if(platform_id == "standard-v3"):
        # cpu
        if(core_fraction == 100):
            add_usage("dn2h2fne3qa9bjv2mm0b", cores * instances_num_ch, resource_name, resource_type) # ClickHouse. Intel Ice Lake. 100% vCPU [core*hour]
        if(core_fraction == 50):
            add_usage("dn2slkf8qnvg3lohvlnk", cores * instances_num_ch, resource_name, resource_type) # ClickHouse. Intel Ice Lake. 50% vCPU [core*hour]
        # ram
        add_usage("dn2cvuiesm49elnni1a5", memory * instances_num_ch, resource_name, resource_type) # ClickHouse. Intel Ice Lake. RAM [gbyte*hour]
    
    if(platform_id == "highfreq-v3"): #! нет в биллинге
        #! ClickHouse. Intel Ice Lake (Compute Optimized). Software accelerated network
        # cpu
        add_usage("dn277ac8ru4ub394msu1", cores * instances_num_ch, resource_name, resource_type) # ClickHouse. Intel Ice Lake (Compute Optimised). 100% vCPU [core*hour]
        # ram
        add_usage("dn2co8sk8cldl5on3ckf", memory * instances_num_ch, resource_name, resource_type) # ClickHouse. Intel Ice Lake (Compute Optimized). RAM [gbyte*hour]

    if(platform_id == "standard-v2"):
        # cpu
        if(core_fraction == 100):
            add_usage("dn2bo4tud2qeo60gr008", cores * instances_num_ch, resource_name, resource_type) # ClickHouse. Intel Cascade Lake. 100% vCPU [core*hour]
        if(core_fraction == 50):
            add_usage("dn2qjtq7ee80fj9c2ot0", cores * instances_num_ch, resource_name, resource_type) # ClickHouse. Intel Cascade Lake. 50% vCPU [core*hour]
        if(core_fraction == 20):
            add_usage("dn24kods372d64lhijmn", cores * instances_num_ch, resource_name, resource_type) # ClickHouse. Intel Cascade Lake. 20% vCPU [core*hour]
        if(core_fraction == 5):
            add_usage("dn2ro2rucgm410h34tiu", cores * instances_num_ch, resource_name, resource_type) # ClickHouse. Intel Cascade Lake. 5% vCPU [core*hour]
        # ram
        add_usage("dn2fol5odat55iak187k", memory * instances_num_ch, resource_name, resource_type) # ClickHouse. Intel Cascade Lake. RAM [gbyte*hour]
    
    if(platform_id == "standard-v1"):
        # cpu
        if(core_fraction == 100):
            add_usage("dn23nulcgejjcs3a5k6c", cores * instances_num_ch, resource_name, resource_type) # ClickHouse. Intel Broadwell. 100% vCPU [core*hour]
        if(core_fraction == 50):
            add_usage("dn27d2sdttppcok68ikt", cores * instances_num_ch, resource_name, resource_type) # ClickHouse. Intel Broadwell. 50% vCPU [core*hour]
        if(core_fraction == 20):
            add_usage("dn20nfs6nvqmsnvjdd5r", cores * instances_num_ch, resource_name, resource_type) # ClickHouse. Intel Broadwell. 20% vCPU [core*hour]
        if(core_fraction == 5):
            add_usage("dn2bl87f2dv7shnmistk", cores * instances_num_ch, resource_name, resource_type) # ClickHouse. Intel Broadwell. 5% vCPU [core*hour]
        # ram
        add_usage("dn2ci1m71mcpuans0njt", memory * instances_num_ch, resource_name, resource_type) # ClickHouse. Intel Broadwell. RAM [gbyte*hour]

    # Zookeeper
    if(platform_id_zk == "standard-v3"):
        if(core_fraction_zk == 100):
            add_usage("dn270b41ltvr4qs6fdu0", cores_zk * instances_num_zk, resource_name, resource_type) # ZooKeeper. Intel Ice Lake. 100% vCPU [core*hour]
        if(core_fraction_zk == 50):
            add_usage("dn28oel39sj8kmfr78lk", cores_zk * instances_num_zk, resource_name, resource_type) # ZooKeeper. Intel Ice Lake. 50% vCPU [core*hour]
        # ram
        add_usage("dn2tg9g6pi4k18isqcq7", memory_zk * instances_num_zk, resource_name, resource_type) # ZooKeeper. Intel Ice Lake. RAM [gbyte*hour]

    if(platform_id_zk == "highfreq-v3"):
        #! ZooKeeper for ClickHouse. Intel Ice Lake (Compute Optimized). Software accelerated network
        add_usage("dn29tpsi73qabnq4m9kb", cores_zk * instances_num_zk, resource_name, resource_type) # ZooKeeper for ClickHouse. Intel Ice Lake (Compute Optimized). 100% vCPU [core*hour]
        # ram
        add_usage("dn2i1lhi7dqj2nah4i2n", memory_zk * instances_num_zk, resource_name, resource_type) # ZooKeeper for ClickHouse. Intel Ice Lake (Compute Optimized). RAM [gbyte*hour]

    if(platform_id_zk == "standard-v2"):
        if(core_fraction_zk == 100):
            add_usage("dn2g6deavckbovip5uu5", cores_zk * instances_num_zk, resource_name, resource_type) # ZooKeeper. Intel Cascade Lake. 100% vCPU [core*hour]
        if(core_fraction_zk == 50):
            add_usage("dn2b40gt80iuh70kfpqc", cores_zk * instances_num_zk, resource_name, resource_type) # ZooKeeper. Intel Cascade Lake. 50% vCPU [core*hour]
        if(core_fraction_zk == 20):
            add_usage("dn2iv9kja0ntvt3uocjm", cores_zk * instances_num_zk, resource_name, resource_type) # ZooKeeper. Intel Cascade Lake. 20% vCPU [core*hour]
        if(core_fraction_zk == 5):
            add_usage("dn2ud13pi583kt52h4jv", cores_zk * instances_num_zk, resource_name, resource_type) # ZooKeeper. Intel Cascade Lake. 5% vCPU [core*hour]
        # ram
        add_usage("dn2hhsaqch2o4tkn1qnk", memory_zk * instances_num_zk, resource_name, resource_type) # ZooKeeper. Intel Cascade Lake. RAM [gbyte*hour]
    
    if(platform_id_zk == "standard-v1"):
        if(core_fraction_zk == 100):
            add_usage("dn2a5pb4kkrvk6ra5vhk", cores_zk * instances_num_zk, resource_name, resource_type) # ZooKeeper. Intel Broadwell. 100% vCPU [core*hour]
        if(core_fraction_zk == 50):
            add_usage("dn29aeejuka6vtvul02s", cores_zk * instances_num_zk, resource_name, resource_type) # ZooKeeper. Intel Broadwell. 50% vCPU [core*hour]
        if(core_fraction_zk == 20):
            add_usage("dn2m7d3nj7qtfhi14gjv", cores_zk * instances_num_zk, resource_name, resource_type) # ZooKeeper. Intel Broadwell. 20% vCPU [core*hour]
        if(core_fraction_zk == 5):
            add_usage("dn2vh46ucftq2ponpe4c", cores_zk * instances_num_zk, resource_name, resource_type) # ZooKeeper. Intel Broadwell. 5% vCPU [core*hour]
        # ram
        add_usage("dn2fg67mc3h26dqfs2s9", memory_zk * instances_num_zk, resource_name, resource_type) # ZooKeeper. Intel Broadwell. RAM [gbyte*hour]

    if(public_ip_num_ch > 0):
        add_usage("dn2riv150c97qbgpik5k", public_ip_num_ch, resource_name, resource_type) # Public IP address - ClickHouse [fip*hour]

    # Clickhouse
    if(disk_type_ch == "network-ssd"):
        add_usage("dn2mvvhqdpp24tm36ks4", disk_size_ch * instances_num_ch, resource_name, resource_type) # Fast network storage \u2014 ClickHouse [gbyte*hour]
    if(disk_type_ch == "network-hdd"):
        add_usage("dn2utn4rqnas617dfa2q", disk_size_ch * instances_num_ch, resource_name, resource_type) # Standard network storage \u2014 ClickHouse [gbyte*hour]
    if(disk_type_ch == "network-ssd-nonreplicated"):
        add_usage("dn2e0j7ko5l58njegum8", disk_size_ch * instances_num_ch, resource_name, resource_type) # Non-replicated fast network storage \u2014 ClickHouse [gbyte*hour]
    if(disk_type_ch == "network-ssd-io-m3"):
        add_usage("dn2lou40il2st50oh4pd", disk_size_ch * instances_num_ch, resource_name, resource_type) # Ultra fast network storage with 3 replicas (SSD) \u2014 ClickHouse [gbyte*hour]
    if(disk_type_ch == "local-ssd"):
        add_usage("dn222q64f5mcjm36ed4q", disk_size_ch * instances_num_ch, resource_name, resource_type) # Fast local storage \u2014 ClickHouse [gbyte*hour]

    # Zookeeper
    if(disk_type_zk == "network-ssd"):
        add_usage("dn2mvvhqdpp24tm36ks4", disk_size_zk * instances_num_zk, resource_name, resource_type) # Fast network storage \u2014 ClickHouse [gbyte*hour]
    if(disk_type_zk == "network-hdd"):
        add_usage("dn2utn4rqnas617dfa2q", disk_size_zk * instances_num_zk, resource_name, resource_type) # Standard network storage \u2014 ClickHouse [gbyte*hour]
    if(disk_type_zk == "network-ssd-nonreplicated"):
        add_usage("dn2e0j7ko5l58njegum8", disk_size_zk * instances_num_zk, resource_name, resource_type) # Non-replicated fast network storage \u2014 ClickHouse [gbyte*hour]
    if(disk_type_zk == "network-ssd-io-m3"):
        add_usage("dn2lou40il2st50oh4pd", disk_size_zk * instances_num_zk, resource_name, resource_type) # Ultra fast network storage with 3 replicas (SSD) \u2014 ClickHouse [gbyte*hour]
    if(disk_type_zk == "local-ssd"):
        add_usage("dn222q64f5mcjm36ed4q", disk_size_zk * instances_num_zk, resource_name, resource_type) # Fast local storage \u2014 ClickHouse [gbyte*hour]

    logging.debug(json.dumps(resource_values, indent=4).replace('\n', '\r'))
    return 0

# yandex_mdb_greenplum_cluster
def process_mdb_greenplum(resource):
    resource_type       = resource["type"]
    resource_name       = resource["name"]
    resource_values     = resource["values"]
    
    master              = resource_values["master_subcluster"][0]
    segment             = resource_values["segment_subcluster"][0]

    disk_size_master           = master["resources"][0].get("disk_size", 0)
    disk_type_master           = master["resources"][0].get("disk_type_id", "network-hdd")
    preset_id_master           = master["resources"][0].get("resource_preset_id", [])
    
    disk_size_segment          = segment["resources"][0].get("disk_size", 0)
    disk_type_segment          = segment["resources"][0].get("disk_type_id", "network-hdd")
    preset_id_segment          = segment["resources"][0].get("resource_preset_id", [])

    try:
        cores_master, core_fraction_master, memory_master, platform_id_master = get_mdb_preset('greenplum', preset_id_master)
    except ValueError as e:
        logging.error(e)
    
    try:
        cores_segment, core_fraction_segment, memory_segment, platform_id_segment = get_mdb_preset('greenplum', preset_id_segment)
    except ValueError as e:
        logging.error(e)

    master_num          = resource_values.get("master_host_count", 0)
    segment_num         = resource_values.get("segment_host_count", 0)
    public_ip_num       = master_num if resource_values.get("assign_public_ip", False) else 0

    # GreenPlum Masters
    if(platform_id_master == "standard-v3"):
        # cpu
        add_usage("dn22vrmol6tmlqmnflh0", cores_master * master_num, resource_name, resource_type) # Greenplum. Intel Ice Lake. 100% vCPU [core*hour]
        # ram
        add_usage("dn2fkkqvmd2dhlo7b07m", memory_master * master_num, resource_name, resource_type) # Greenplum. Intel Ice Lake. RAM [gbyte*hour]

    #! добавить highfreq платформу
    if(platform_id_master == "highfreq-v3"):
        # cpu
        add_usage("dn21dgdltqrgdsodkm4i", cores_master * master_num, resource_name, resource_type) # Greenplum. Intel Ice Lake (Compute Optimized). 100% vCPU [core*hour]
        # ram
        add_usage("dn2hom6ljm6s2js93o40", memory_master * master_num, resource_name, resource_type) # Greenplum. Intel Ice Lake (Compute Optimized). RAM [gbyte*hour]
    
    if(platform_id_master == "standard-v2"):
        # cpu
        add_usage("dn27vfbvh9mtobabcvd3", cores_master * master_num, resource_name, resource_type) # Greenplum. Intel Cascade Lake. 100% vCPU [core*hour]
        # ram
        add_usage("dn2gbhl2hc3aun6t7dgm", memory_master * master_num, resource_name, resource_type) # Greenplum. Intel Cascade Lake. RAM [gbyte*hour]
    
    if(public_ip_num > 0):
        add_usage("dn2gikj1nkrl5epq2ivi", public_ip_num, resource_name, resource_type) # Public IP address - Greenplum [fip*hour]

    if(disk_type_master == "network-ssd"):
        add_usage("dn24ljti6nor6rm64n98", disk_size_master * master_num, resource_name, resource_type) # Fast network storage \u2014 Greenplum [gbyte*hour]
    if(disk_type_master == "network-hdd"):
        add_usage("dn2amtenb2bmhm5r3t26", disk_size_master * master_num, resource_name, resource_type) # Standard network storage \u2014 Greenplum [gbyte*hour]
    if(disk_type_master == "network-ssd-nonreplicated"):
        add_usage("dn281sknb94nk6dhg5f1", disk_size_master * master_num, resource_name, resource_type) # Non-replicated fast network storage \u2014 Greenplum [gbyte*hour]
    if(disk_type_master == "network-ssd-io-m3"):
        add_usage("dn2q30eprodapfghra4q", disk_size_master * master_num, resource_name, resource_type) # Ultra fast network storage with 3 replicas (SSD) \u2014 Greenplum [gbyte*hour]
    if(disk_type_master == "local-ssd"):
        add_usage("dn23vk0nguhc9qe9v30c", disk_size_master * master_num, resource_name, resource_type) # Fast local storage \u2014 Greenplum [gbyte*hour]
    
    # GreenPlum Segments
    if(platform_id_segment == "standard-v3"):
        # cpu
        add_usage("dn22vrmol6tmlqmnflh0", cores_segment * segment_num, resource_name, resource_type) # Greenplum. Intel Ice Lake. 100% vCPU [core*hour]
        # ram
        add_usage("dn2fkkqvmd2dhlo7b07m", memory_segment * segment_num, resource_name, resource_type) # Greenplum. Intel Ice Lake. RAM [gbyte*hour]

    #! добавить highfreq платформу
    if(platform_id_segment == "highfreq-v3"):
        # cpu
        add_usage("dn21dgdltqrgdsodkm4i", cores_segment * segment_num, resource_name, resource_type) # Greenplum. Intel Ice Lake (Compute Optimized). 100% vCPU [core*hour]
        # ram
        add_usage("dn2hom6ljm6s2js93o40", memory_segment * segment_num, resource_name, resource_type) # Greenplum. Intel Ice Lake (Compute Optimized). RAM [gbyte*hour]

    if(platform_id_segment == "standard-v2"):
        # cpu
        add_usage("dn27vfbvh9mtobabcvd3", cores_segment * segment_num, resource_name, resource_type) # Greenplum. Intel Cascade Lake. 100% vCPU [core*hour]
        # ram
        add_usage("dn2gbhl2hc3aun6t7dgm", memory_segment * segment_num, resource_name, resource_type) # Greenplum. Intel Cascade Lake. RAM [gbyte*hour]

    if(disk_type_segment == "network-ssd"):
        add_usage("dn24ljti6nor6rm64n98", disk_size_segment * segment_num, resource_name, resource_type) # Fast network storage \u2014 Greenplum [gbyte*hour]
    if(disk_type_segment == "network-hdd"):
        add_usage("dn2amtenb2bmhm5r3t26", disk_size_segment * segment_num, resource_name, resource_type) # Standard network storage \u2014 Greenplum [gbyte*hour]
    if(disk_type_segment == "network-ssd-nonreplicated"):
        add_usage("dn281sknb94nk6dhg5f1", disk_size_segment * segment_num, resource_name, resource_type) # Non-replicated fast network storage \u2014 Greenplum [gbyte*hour]
    if(disk_type_segment == "network-ssd-io-m3"):
        add_usage("dn2q30eprodapfghra4q", disk_size_segment * segment_num, resource_name, resource_type) # Ultra fast network storage with 3 replicas (SSD) \u2014 Greenplum [gbyte*hour]
    if(disk_type_segment == "local-ssd"):
        add_usage("dn23vk0nguhc9qe9v30c", disk_size_segment * segment_num, resource_name, resource_type) # Fast local storage \u2014 Greenplum [gbyte*hour]

    logging.debug(json.dumps(resource_values, indent=4).replace('\n', '\r'))
    return 0

# yandex_mdb_kafka_cluster
def process_mdb_kafka(resource):
    resource_type           = resource["type"]
    resource_name           = resource["name"]
    resource_values         = resource["values"]

    disk_size               = resource_values["config"][0]["kafka"][0]["resources"][0].get("disk_size", 0)
    disk_type               = resource_values["config"][0]["kafka"][0]["resources"][0].get("disk_type_id", "network-hdd")
    preset_id               = resource_values["config"][0]["kafka"][0]["resources"][0].get("resource_preset_id", [])

    if resource_values["config"][0].get("zookeeper"):
        disk_size_zk            = resource_values["config"][0]["zookeeper"][0]["resources"][0].get("disk_size", 0)
        disk_type_zk            = resource_values["config"][0]["zookeeper"][0]["resources"][0].get("disk_type_id", "network-hdd")
        preset_id_zk            = resource_values["config"][0]["zookeeper"][0]["resources"][0].get("resource_preset_id", [])

        try:
            cores_zk, core_fraction_zk, memory_zk, platform_id_zk = get_mdb_preset('kafka', preset_id_zk)
        except ValueError as e:
            logging.error(e)

        if(platform_id_zk == "standard-v3"):
            # cpu
            if(core_fraction_zk == 100):
                add_usage("dn2nhhb7jic2747airrn", cores_zk * 3, resource_name, resource_type) # ZooKeeper for Apache Kafka\u00ae. Intel Ice Lake. 100% vCPU [core*hour]
            if(core_fraction_zk == 50):
                add_usage("dn2gsmai0ju430119mqj", cores_zk * 3, resource_name, resource_type) # ZooKeeper for Apache Kafka\u00ae. Intel Ice Lake. 50% vCPU [core*hour]
            # ram
            add_usage("dn2r01fpbih17tae9m00", cores_zk * 3, resource_name, resource_type) # ZooKeeper for Apache Kafka\u00ae. Intel Ice Lake. RAM [gbyte*hour]

        #! добавить highfreq платформу
        if(platform_id_zk == "highfreq-v3"):
            # ZooKeeper for Apache Kafka\u00ae. Intel Ice Lake (Compute Optimized). Software accelerated network
            # cpu
            add_usage("dn2prkfjerh1oh1km220", cores_zk * 3, resource_name, resource_type) # ZooKeeper for Apache Kafka\u00ae. Intel Ice Lake (Compute Optimized). 100% vCPU [core*hour]
            # ram
            add_usage("dn2un2g6tou5jrg18j3d", cores_zk * 3, resource_name, resource_type) # ZooKeeper for Apache Kafka\u00ae. Intel Ice Lake (Compute Optimized). RAM [gbyte*hour]

        if(platform_id_zk == "standard-v2"):
            # cpu
            if(core_fraction_zk == 100):
                add_usage("dn2rqdpeh829k7prtfng", cores_zk * 3, resource_name, resource_type) # ZooKeeper for Apache Kafka\u00ae. Intel Cascade Lake. 100% vCPU [core*hour]
            if(core_fraction_zk == 50):
                add_usage("dn2oobqd83ld4uucdr5g", cores_zk * 3, resource_name, resource_type) # ZooKeeper for Apache Kafka\u00ae. Intel Cascade Lake. 50% vCPU [core*hour]
            # ram
            add_usage("dn2kd8egpcfqmm4b9f1m", memory_zk * 3, resource_name, resource_type) # ZooKeeper for Apache Kafka\u00ae. Intel Cascade Lake. RAM [gbyte*hour]

        if(disk_type_zk == "network-ssd"):
            add_usage("dn2du1uuuvjdqdpmsmsd", disk_size_zk * 3, resource_name, resource_type) # Fast network storage \u2014 Apache Kafka\u00ae [gbyte*hour]
        if(disk_type_zk == "network-hdd"):
            add_usage("dn28vvrfmvdd2a9vhfus", disk_size_zk * 3, resource_name, resource_type) # Standard network storage \u2014 Apache Kafka\u00ae [gbyte*hour]
        if(disk_type_zk == "network-ssd-nonreplicated"):
            add_usage("dn278mhc61kqavrjh26u", disk_size_zk * 3, resource_name, resource_type) # Non-replicated fast network storage \u2014 Apache Kafka\u00ae [gbyte*hour]
        if(disk_type_zk == "network-ssd-io-m3"):
            add_usage("dn25ksor7p112bvs2qts", disk_size_zk * 3, resource_name, resource_type) # Ultra fast network storage with 3 replicas (SSD) \u2014 Apache Kafka\u00ae [gbyte*hour]
        if(disk_type_zk == "local-ssd"):
            add_usage("dn26m07r3n3lfhu0sshg", disk_size_zk * 3, resource_name, resource_type) # Fast local storage \u2014 Apache Kafka\u00ae [gbyte*hour]
        
    instance_num            = resource_values["config"][0].get("brokers_count", 1)
    public_ip_num           = instance_num if resource_values["config"][0].get("assign_public_ip", False) else 0

    try:
        cores, core_fraction, memory, platform_id = get_mdb_preset('kafka', preset_id)
    except ValueError as e:
        logging.error(e)

    if(platform_id == "standard-v3"):
        # cpu
        if(core_fraction == 100):
            add_usage("dn24mf6m837qdtfaus9o", cores * instance_num, resource_name, resource_type) # Apache Kafka\u00ae. Intel Ice Lake. 100% vCPU [core*hour]
        if(core_fraction == 50):
            add_usage("dn2j1e6ag4ebi1lqhpb5", cores * instance_num, resource_name, resource_type) # Apache Kafka\u00ae. Intel Ice Lake. 50% vCPU [core*hour]
        # ram
        add_usage("dn2ftqohv8psorjabi12", memory * instance_num, resource_name, resource_type) # Apache Kafka\u00ae. Intel Ice Lake. RAM [gbyte*hour]

    #! добавить highfreq платформу
    if(platform_id == "highfreq-v3"):
        # Apache Kafka\u00ae. Intel Ice Lake (Compute Optimized). Software accelerated network
        # cpu
        add_usage("dn2u61ode72vg51luvm5", cores * instance_num, resource_name, resource_type) # Apache Kafka\u00ae. Intel Ice Lake (Compute Optimized). 100% vCPU [core*hour]
        # ram
        add_usage("dn2u83rsns5m0bdk8pra", cores * instance_num, resource_name, resource_type) # Apache Kafka\u00ae. Intel Ice Lake (Compute Optimized). RAM [gbyte*hour]

    if(platform_id == "standard-v2"):
        # cpu
        if(core_fraction == 100):
            add_usage("dn20mtnp2jnjj4km7u5g", cores * instance_num, resource_name, resource_type) # Apache Kafka\u00ae. Intel Cascade Lake. 100% vCPU [core*hour]
        if(core_fraction == 50):
            add_usage("dn25ij9c6ncskqe2v804", cores * instance_num, resource_name, resource_type) # Apache Kafka\u00ae. Intel Cascade Lake. 50% vCPU [core*hour]
        # ram
        add_usage("dn29ei2iq0joi59033pb", memory * instance_num, resource_name, resource_type) # Apache Kafka\u00ae. Intel Cascade Lake. RAM [gbyte*hour]

    if(public_ip_num > 0):
        add_usage("dn2kol05hvp3tj76pqep", public_ip_num, resource_name, resource_type) # Public IP address - Apache Kafka\u00ae [fip*hour]

    if(disk_type == "network-ssd"):
        add_usage("dn2du1uuuvjdqdpmsmsd", disk_size * instance_num, resource_name, resource_type) # Fast network storage \u2014 Apache Kafka\u00ae [gbyte*hour]
    if(disk_type == "network-hdd"):
        add_usage("dn28vvrfmvdd2a9vhfus", disk_size * instance_num, resource_name, resource_type) # Standard network storage \u2014 Apache Kafka\u00ae [gbyte*hour]
    if(disk_type == "network-ssd-nonreplicated"):
        add_usage("dn278mhc61kqavrjh26u", disk_size * instance_num, resource_name, resource_type) # Non-replicated fast network storage \u2014 Apache Kafka\u00ae [gbyte*hour]
    if(disk_type == "network-ssd-io-m3"):
        add_usage("dn25ksor7p112bvs2qts", disk_size * instance_num, resource_name, resource_type) # Ultra fast network storage with 3 replicas (SSD) \u2014 Apache Kafka\u00ae [gbyte*hour]
    if(disk_type == "local-ssd"):
        add_usage("dn26m07r3n3lfhu0sshg", disk_size * instance_num, resource_name, resource_type) # Fast local storage \u2014 Apache Kafka\u00ae [gbyte*hour]

    logging.debug(json.dumps(resource_values, indent=4).replace('\n', '\r'))
    return 0

# yandex_mdb_redis_cluster
def process_mdb_redis(resource):
    resource_type       = resource["type"]
    resource_name       = resource["name"]
    resource_values     = resource["values"]

    disk_size           = resource_values["resources"][0].get("disk_size", 0)
    disk_type           = resource_values["resources"][0].get("disk_type_id", "network-ssd")
    preset_id           = resource_values["resources"][0].get("resource_preset_id", [])
    instances           = resource_values.get("host", [])

    try:
        cores, core_fraction, memory, platform_id = get_mdb_preset('redis', preset_id)
    except ValueError as e:
        logging.error(e)

    instance_num        = len(instances)
    public_ip_num       = sum(1 for instance in instances if instance.get("assign_public_ip") is True)

    if(platform_id == "standard-v3"):
        # cpu
        if(core_fraction == 100):
            add_usage("dn2qrqp6uho94a80hgr3", cores * instance_num, resource_name, resource_type) # Redis. Intel Ice Lake. 100% vCPU [core*hour]
        if(core_fraction == 50):
            add_usage("dn2olfc9i989aj43sdh9xx", cores * instance_num, resource_name, resource_type) # Redis. Intel Ice Lake. 50% vCPU [core*hour]
        # ram
        add_usage("dn2i5hfnisk3mg4rkl0v", memory * instance_num, resource_name, resource_type) # Redis. Intel Ice Lake. RAM [gbyte*hour]

    #! добавить highfreq платформу
    if(platform_id == "highfreq-v3"):
        #! Redis. Intel Ice Lake (Compute Optimized). Software accelerated network
        # cpu
        add_usage("dn2p5vd4ccc8i53ia6bi", cores * instance_num, resource_name, resource_type) # Redis. Intel Ice Lake (Compute Optimized). 100% vCPU [core*hour]
        # ram
        add_usage("dn2sf9026ldfpoaflvju", memory * instance_num, resource_name, resource_type) # Redis. Intel Ice Lake (Compute Optimized). RAM [gbyte*hour]

    if(platform_id == "standard-v2"):
        # cpu
        if(core_fraction == 100):
            add_usage("dn266b8r1i07682ojiiq", cores * instance_num, resource_name, resource_type) # Redis. Intel Cascade Lake. 100% vCPU [core*hour]
        if(core_fraction == 50):
            add_usage("dn26opl99hcbjqvo87gf", cores * instance_num, resource_name, resource_type) # Redis. Intel Cascade Lake. 50% vCPU [core*hour]
        if(core_fraction == 5):
            add_usage("dn2qgqnuuucr2uat9be2", cores * instance_num, resource_name, resource_type) # Redis. Intel Cascade Lake. 5% vCPU [core*hour]
        # ram
        add_usage("dn2gac3fpk1bsurdkf0h", memory * instance_num, resource_name, resource_type) # Redis. Intel Cascade Lake. RAM [gbyte*hour]
    
    if(platform_id == "standard-v1"):
        # cpu
        if(core_fraction == 100):
            add_usage("dn2ta4lgerp02btumaic", cores * instance_num, resource_name, resource_type) # Redis. Intel Broadwell. 100% vCPU [core*hour]
        if(core_fraction == 20):
            add_usage("dn29cjcghhc5ihatrc35", cores * instance_num, resource_name, resource_type) # Redis. Intel Broadwell. 20% vCPU [core*hour]
        if(core_fraction == 5):
            add_usage("dn2gvhqj7nimn9jaofi0", cores * instance_num, resource_name, resource_type) # Redis. Intel Broadwell. 5% vCPU [core*hour]
        # ram
        add_usage("dn24sref9ucjdo6ut46k", memory * instance_num, resource_name, resource_type) # Redis. Intel Broadwell. RAM [gbyte*hour]

    if(public_ip_num > 0):
        add_usage("dn21adn8pgvr7hr9jhh3", public_ip_num, resource_name, resource_type) # Public IP address - Redis [fip*hour]

    if(disk_type == "network-ssd"):
        add_usage("dn2brvmhtb2i0o7gchn6", disk_size * instance_num, resource_name, resource_type) # Fast network storage \u2014 Redis [gbyte*hour]
    if(disk_type == "network-ssd-nonreplicated"):
        add_usage("dn265o7f5n5dh8pcdes5", disk_size * instance_num, resource_name, resource_type) # Non-replicated fast network storage \u2014  [gbyte*hour]
    if(disk_type == "network-ssd-io-m3"):
        add_usage("dn2jbe8pp30806tb8dev", disk_size * instance_num, resource_name, resource_type) # Ultra fast network storage with 3 replicas (SSD) \u2014  [gbyte*hour]
    if(disk_type == "local-ssd"):
        add_usage("dn2b2d8c9e60npmqq41k", disk_size * instance_num, resource_name, resource_type) # Fast local storage \u2014 Redis [gbyte*hour]

    logging.debug(json.dumps(resource_values, indent=4).replace('\n', '\r'))
    return 0

# yandex_mdb_opensearch_cluster
def process_mdb_openseach_nodegroup(nodegroup, resource_name, resource_type):
    BYTES_IN_GIGABYTE = 1024 * 1024 * 1024

    instance_num = nodegroup.get("hosts_count", 1)
    public_ip_num = instance_num if nodegroup.get("assign_public_ip") else 0

    disk_size           = round(nodegroup["resources"].get("disk_size", 0) / BYTES_IN_GIGABYTE) #! why it has to be in bytes?
    disk_type           = nodegroup["resources"].get("disk_type_id", "network-hdd")
    preset_id           = nodegroup["resources"].get("resource_preset_id", [])

    try:
        cores, core_fraction, memory, platform_id = get_mdb_preset('opensearch', preset_id)
    except ValueError as e:
        logging.error(e)

    if(platform_id == "standard-v3"):
        # cpu
        if(core_fraction == 100):
            add_usage("dn2rf1bupkvgk646cpqo", cores * instance_num, resource_name, resource_type) # OpenSearch. Intel Ice Lake. 100% vCPU [core*hour]
        if(core_fraction == 50):
            add_usage("dn2jeuof2ujtjeadau6i", cores * instance_num, resource_name, resource_type) # OpenSearch. Intel Ice Lake. 50% vCPU [core*hour]
        # ram
        add_usage("dn22dhakdgfrijul4v1f", memory * instance_num, resource_name, resource_type) # OpenSearch. Intel Ice Lake. RAM [gbyte*hour]

    if(platform_id == "highfreq-v3"):
        # OpenSearch. Intel Ice Lake (Compute Optimized). Software accelerated network
        # cpu
        add_usage("dn2p79o9d7r4tdm1s1jr", cores * instance_num, resource_name, resource_type) # OpenSearch. Intel Ice Lake (Compute Optimised). 100% vCPU [core*hour]
        # ram
        add_usage("dn2ko90o5lnvcgc0u6km", memory * instance_num, resource_name, resource_type) # OpenSearch. Intel Ice Lake (Compute Optimized). RAM [gbyte*hour]

    if(platform_id == "standard-v2"):
        # cpu
        if(core_fraction == 100):
            add_usage("dn211hvm5bgm4dl0gblv", cores * instance_num, resource_name, resource_type) # OpenSearch. Intel Cascade Lake. 100% vCPU [core*hour]
        if(core_fraction == 50):
            add_usage("dn2l6h3sovqem675uih2", cores * instance_num, resource_name, resource_type) # OpenSearch. Intel Cascade Lake. 50% vCPU [core*hour]
        # ram
        add_usage("dn2uga61a66rcda0igtk", memory * instance_num, resource_name, resource_type) # OpenSearch. Intel Cascade Lake. RAM [gbyte*hour]

    if(public_ip_num > 0):
        add_usage("dn2mqb0g06ogqnsinbt2", public_ip_num, resource_name, resource_type) # Public IP address - OpenSearch [fip*hour]

    if(disk_type == "network-ssd"):
        add_usage("dn28u08us0otvnpd7tiu", disk_size * instance_num, resource_name, resource_type) # Fast network storage \u2014 OpenSearch [gbyte*hour]
    if(disk_type == "network-hdd"):
        add_usage("dn217fio8e4jq2bb93va", disk_size * instance_num, resource_name, resource_type) # Standard network storage \u2014 OpenSearch [gbyte*hour]
    if(disk_type == "network-ssd-nonreplicated"):
        add_usage("dn2gt4e75hm80bpgk8i7", disk_size * instance_num, resource_name, resource_type) # Non-replicated fast network storage \u2014 OpenSearch [gbyte*hour]
    if(disk_type == "network-ssd-io-m3"):
        add_usage("dn2690d7uj1the1vaggf", disk_size * instance_num, resource_name, resource_type) # Ultra fast network storage with 3 replicas (SSD) \u2014 OpenSearch [gbyte*hour]
    if(disk_type == "local-ssd"):
        add_usage("dn2dnba7orfgdag64gmh", disk_size * instance_num, resource_name, resource_type) # Fast local storage \u2014 OpenSearch [gbyte*hour]
    
    return 0

def process_mdb_opensearch(resource):
    resource_type       = resource["type"]
    resource_name       = resource["name"]
    resource_values     = resource["values"]

    node_groups         = resource_values["config"]["opensearch"].get("node_groups", [])
    dashboards          = resource_values["config"]["dashboards"].get("node_groups", [])

    for node_group in node_groups + dashboards:
        process_mdb_openseach_nodegroup(node_group, resource_name, resource_type)

    logging.debug(json.dumps(resource_values, indent=4).replace('\n', '\r'))
    return 0

# yandex_ydb_database_dedicated
def process_mdb_ydb(resource):
    resource_type       = resource["type"]
    resource_name       = resource["name"]
    resource_values     = resource["values"]

    disk_size           = resource_values["storage_config"][0].get("group_count", 0) * 100
    preset_id           = resource_values.get("resource_preset_id", [])

    try:
        cores, core_fraction, memory, platform_id = get_mdb_preset('ydb', preset_id)
    except ValueError as e:
        logging.error(e)

    instance_num        = resource_values["scale_policy"][0]["fixed_scale"][0].get("size", 1)

    # cpu
    add_usage("dn2uh84ab9ga5954i807", cores * instance_num, resource_name, resource_type) # YDB. Intel Cascade Lake. 100% vCPU [core*hour]
    # ram
    add_usage("dn24ok7m82d8uhe9g725", memory * instance_num, resource_name, resource_type) # YDB. Intel Cascade Lake. RAM [gbyte*hour]
    # disk
    add_usage("dn26b206u8r13m8go6d2", disk_size * instance_num, resource_name, resource_type) # YDB. Fast storage [gbyte*hour]

    logging.debug(json.dumps(resource_values, indent=4).replace('\n', '\r'))
    return 0

# yandex_vpc_address
def process_vpc_address(resource):
    resource_type       = resource["type"]
    resource_name       = resource["name"]
    resource_values     = resource["values"]

    if resource_values.get("external_ipv4_address"):
        add_usage("dn229q5mnmp58t58tfel", 1, resource_name, resource_type) # Public IP address [gbyte*hour]

    return 0

# Processing terraform plan
def process_plan(tf_plan, param_full):

    usage.clear()

    for resource in tf_plan["planned_values"]["root_module"]["resources"]:
        if(resource["type"]     == "yandex_compute_instance"):
            process_vm(resource)
            logging.info(f'{resource["type"]} is processed.')
        elif(resource["type"]   == "yandex_compute_instance_group"):
            process_vm_group(resource)
            logging.info(f'{resource["type"]} is processed.')
        elif(resource["type"]   == "yandex_compute_disk"):
            process_vm_disk(resource)
            logging.info(f'{resource["type"]} is processed.')
        elif(resource["type"]   == "yandex_compute_filesystem"):
            process_filesystem(resource)
            logging.info(f'{resource["type"]} is processed.')
        elif(resource["type"]   == "yandex_kubernetes_cluster"):
            process_kube_cluster(resource)
            logging.info(f'{resource["type"]} is processed.')
        elif(resource["type"]   == "yandex_kubernetes_node_group"):
            process_kube_node(resource)
            logging.info(f'{resource["type"]} is processed.')
        elif(resource["type"]   == "yandex_mdb_mysql_cluster"):
            process_mdb_mysql(resource)
            logging.info(f'{resource["type"]} is processed.')
        elif(resource["type"]   == "yandex_mdb_postgresql_cluster"):
            process_mdb_postgre(resource)
            logging.info(f'{resource["type"]} is processed.')
        elif(resource["type"]   == "yandex_mdb_clickhouse_cluster"):
            process_mdb_clickhouse(resource)
            logging.info(f'{resource["type"]} is processed.')
        elif(resource["type"]   == "yandex_mdb_greenplum_cluster"):
            process_mdb_greenplum(resource)
            logging.info(f'{resource["type"]} is processed.')
        elif(resource["type"]   == "yandex_mdb_kafka_cluster"):
            process_mdb_kafka(resource)
            logging.info(f'{resource["type"]} is processed.')
        elif(resource["type"]   == "yandex_mdb_redis_cluster"):
            process_mdb_redis(resource)
            logging.info(f'{resource["type"]} is processed.')
        elif(resource["type"]   == "yandex_mdb_opensearch_cluster"):
            process_mdb_opensearch(resource)
            logging.info(f'{resource["type"]} is processed.')
        elif(resource["type"]   == "yandex_ydb_database_dedicated"):
            process_mdb_ydb(resource)
            logging.info(f'{resource["type"]} is processed.')
        elif(resource["type"]   == "yandex_vpc_address"):
            process_vpc_address(resource)
            logging.info(f'{resource["type"]} is processed.')
        # 
        else:
            logging.info(f'{resource["type"]} is ignored.')

        # yandex_mdb_mongodb_cluster
        # yandex_dataproc_cluster

    # Getting the results
    hourly_rate     = calculate_total(usage, prices)
    monthly_rate    = hourly_rate * 24 * 31

    if param_full:
        return {"hourly": round(hourly_rate, 2), "monthly": round(monthly_rate,2), "currency": "RUB", "usage": get_usage()}
    else:
        return {"hourly": round(hourly_rate, 2), "monthly": round(monthly_rate,2), "currency": "RUB"}

def main():
    parser = argparse.ArgumentParser(description="Process a JSON file")
    parser.add_argument("json_file", help="Path to the JSON file")
    args = parser.parse_args()

    try:
        with open(args.json_file, 'r') as f:
            data = json.load(f)
            process_plan(data, False)
    except FileNotFoundError:
        print(f"File {args.json_file} not found.")
    except json.JSONDecodeError:
        print("Failed to decode JSON. Please check the file format.")
    
    # Getting the results
    hourly_rate     = calculate_total(usage, prices)
    monthly_rate    = hourly_rate * 24 * 31 

    print_usage()
    print(f"Hourly: {round(hourly_rate, 2)} RUB / Monthly: {round(monthly_rate,2)} RUB")

if __name__ == "__main__":
    main()