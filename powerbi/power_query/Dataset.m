let
    Source = DatabricksMultiCloud.Catalogs(
        DatabricksServerHostname,
        DatabricksHttpPath,
        [Catalog = null, Database = null, EnableAutomaticProxyDiscovery = null, Implementation = "2.0"]
    ),
    Catalog = Source{[Name = DatabricksCatalog, Kind = "Database"]}[Data],
    Gold = Catalog{[Name = "gold", Kind = "Schema"]}[Data],
    PublishedQualityView = Gold{[Name = "vw_powerbi_date_set_quality", Kind = "View"]}[Data]
in
    PublishedQualityView
