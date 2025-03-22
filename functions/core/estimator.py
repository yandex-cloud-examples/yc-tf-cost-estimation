import logging
from service.pricing import PricingService
from service.resource_spec import ResourceSpecService
from model.usage import UsageCollector
from processor import ProcessorRegistry

class TerraformCostEstimator:
    """Main application class for estimating Terraform costs"""
    
    def __init__(self, pricing_service, resource_spec_service):
        self.pricing_service = pricing_service
        self.resource_spec_service = resource_spec_service
        self.processor_registry = ProcessorRegistry(self.pricing_service, self.resource_spec_service)
    
    def process_plan(self, tf_plan, param_full):
        """Process a Terraform plan and estimate costs"""
        usage_collector = UsageCollector(self.pricing_service)
        usage_collector.clear()
        
        for resource in tf_plan["planned_values"]["root_module"]["resources"]:
            resource_type = resource["type"]
            processor = self.processor_registry.get_processor(resource_type)
            
            if processor:
                processor.process(resource, usage_collector)
                logging.info(f'{resource_type} is processed.')
            else:
                logging.info(f'{resource_type} is ignored.')
        
        hourly_rate = usage_collector.calculate_total()
        monthly_rate = hourly_rate * 24 * 31
        
        if param_full:
            return {
                "hourly": round(hourly_rate, 2),
                "monthly": round(monthly_rate, 2),
                "currency": "RUB",
                "usage": usage_collector.get_usage()
            }
        else:
            return {
                "hourly": round(hourly_rate, 2),
                "monthly": round(monthly_rate, 2),
                "currency": "RUB"
            }
    
    def get_usage_collector(self):
        """Create and return a new usage collector"""
        return UsageCollector(self.pricing_service)
