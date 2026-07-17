Glue module that adds Operating Unit support to the Consulting module.
Extends ``consulting_service``, ``consulting_service.business_process``,
``consulting_service.business_process_area``,
``consulting_service.document_extraction``,
``consulting_service.document_type``, ``consulting_service.entity``,
``consulting_service.issue``, and
``consulting_service.materialized_view`` with
``mixin.single_operating_unit``, adding the ``operating_unit_id`` field,
security groups/rules, and view integration.
