let
    Source = #"Regional KPI",
    RegionColumns = Table.SelectColumns(
        Source,
        {"analysis_region_sk", "analysis_region_code", "analysis_region_name"}
    ),
    UniqueRegions = Table.Distinct(RegionColumns),
    PresentationNames = Table.AddColumn(
        UniqueRegions,
        "analysis_region_display_name",
        each
            let
                RegionCode = [analysis_region_code],
                GenericName = Text.Combine(
                    List.Transform(
                        Text.Split([analysis_region_name], ","),
                        each Text.Proper(Text.Trim(_))
                    ),
                    ", "
                )
            in
                if RegionCode = "09162" then "München, Stadt"
                else if RegionCode = "05111" then "Düsseldorf, Stadt"
                else if RegionCode = "05378" then "Rheinisch-Bergischer Kreis"
                else if RegionCode = "06415" then "Hanau, Stadt"
                else if RegionCode = "07211" then "Trier-Saarburg"
                else if RegionCode = "07317" then "Pirmasens, Stadt"
                else if RegionCode = "08111" then "Stuttgart, Stadt"
                else GenericName,
        type text
    )
in
    PresentationNames
