# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Estimation based on Terraform state.
- Deeper Terraform integration for getting estimations in Terraform outputs.

## [1.0.1] - 2025-02-09

### Added

- Fixed `get-sku.py` script that generates the `sku.json` file.
- Refreshed sku bindings in compute services so that GPUs can be calculated as usual.

## [1.0.0] - 2024-09-06

### Added

- Estimation based on Terraform plan: local estimation and remote estimation.
- Terraform module for deploying the script in Yandex Cloud.