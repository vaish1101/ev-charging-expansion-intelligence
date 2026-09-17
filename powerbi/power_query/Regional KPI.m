let
    Source = DatabricksMultiCloud.Catalogs(
        DatabricksServerHostname,
        DatabricksHttpPath,
        [Catalog = null, Database = null, EnableAutomaticProxyDiscovery = null, Implementation = "2.0"]
    ),
    Catalog = Source{[Name = DatabricksCatalog, Kind = "Database"]}[Data],
    Gold = Catalog{[Name = "gold", Kind = "Schema"]}[Data],
    PublishedView = Gold{[Name = "vw_powerbi_region_kpi_published", Kind = "View"]}[Data],
    SelectedColumns = Table.SelectColumns(
        PublishedView,
        {
            "date_set_id",
            "analysis_region_sk",
            "analysis_region_code",
            "analysis_region_name",
            "registered_bev_passenger_car_stock",
            "registered_passenger_car_stock",
            "bev_penetration_percent",
            "in_service_registered_charging_facilities",
            "in_service_registered_charging_points",
            "in_service_registered_normal_charging_points",
            "in_service_registered_fast_charging_points",
            "in_service_registered_unclassified_charging_points",
            "in_service_registered_facility_nominal_power_kw",
            "in_service_registered_charging_points_per_1000_bevs",
            "in_service_registered_fast_charging_points_per_1000_bevs",
            "in_service_registered_charging_facilities_per_1000_bevs",
            "in_service_registered_facility_nominal_power_kw_per_1000_bevs",
            "bev_denominator_quality_reason",
            "kpi_12_unit",
            "quality_status",
            "kba_reference_date",
            "bnetza_reference_date",
            "destatis_reference_date",
            "kba_to_bnetza_lag_days",
            "publication_state",
            "date_set_label"
        }
    )
in
    SelectedColumns
