import json
import argparse
import logging
from core.container import Container
from util.logging import configure_logging

def process_plan_command():
    """Command-line interface for processing Terraform plans"""
    parser = argparse.ArgumentParser(description="Process a Terraform plan JSON file")
    parser.add_argument("json_file", help="Path to the JSON file")
    args = parser.parse_args()

    # Initialize logging
    configure_logging(logging.INFO)
    
    # Get container and services
    container = Container.get_instance()
    container.initialize()
    estimator = container.get('estimator')
    
    try:
        with open(args.json_file, 'r') as f:
            data = json.load(f)
            result = estimator.process_plan(data, False)
            
            # Create a usage collector for printing
            usage_collector = estimator.get_usage_collector()
            for resource in data["planned_values"]["root_module"]["resources"]:
                resource_type = resource["type"]
                processor = estimator.processor_registry.get_processor(resource_type)
                if processor:
                    processor.process(resource, usage_collector)
            
            usage_collector.print_usage()
            print(f"Hourly: {result['hourly']} RUB / Monthly: {result['monthly']} RUB")
    except FileNotFoundError:
        print(f"File {args.json_file} not found.")
    except json.JSONDecodeError:
        print("Failed to decode JSON. Please check the file format.")
