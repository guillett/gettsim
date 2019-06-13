import numpy as np
import pandas as pd


def tax_sched(df, tb):
    """Given various forms of income and other state variables, return
    the different taxes to be paid before making favourability checks etc..

    In particular

        * Income tax (Einkommensteuer)
        * Solidarity Surcharge (Solidaritätszuschlag)
        * Capital income tax (Abgeltungssteuer)

    """

    adult_married = (~df["child"]) & (df["zveranl"])
    # create ts dataframe and copy three important variables
    ts = pd.DataFrame(index=df.index.copy())
    for inc in tb["zve_list"]:
        ts["tax_" + inc] = tb["tax_schedule"](df["zve_" + inc], tb)
        ts["tax_{}_tu".format(inc)] = ts["tax_{}".format(inc)]
        ts.loc[adult_married, "tax_{}_tu".format(inc)] = ts["tax_{}".format(inc)][
            adult_married
        ].sum()

    # Abgeltungssteuer
    ts["abgst"] = abgeltung(df, tb)
    ts["abgst_tu"] = 0
    ts.loc[adult_married, "abgst_tu"] = ts["abgst"][adult_married].sum()

    """Solidarity Surcharge. on top of the income tax and capital income tax.
    No Soli if income tax due is below € 920 (solifreigrenze)
    Then it increases with 0.2 marginal rate until 5.5% (solisatz)
    of the incometax is reached.
    As opposed to the 'standard' income tax,
    child allowance is always deducted for soli calculation
    """

    if tb["yr"] >= 1991:
        ts["solibasis"] = ts["tax_kfb_tu"] + ts["abgst_tu"]
        # Soli also in monthly terms. only for adults
        ts["soli_tu"] = soli_formula(ts["solibasis"], tb) * ~df["child"] * (1 / 12)
    else:
        ts["soli_tu"] = 0

    # Assign Soli to individuals
    ts["soli"] = np.select(
        [df["zveranl"], ~df["zveranl"]], [ts["soli_tu"] / 2, ts["soli_tu"]]
    )
    print(df["tu_id"])
    print(ts[["tax_kfb_tu", "tax_kfb", "soli", "solibasis", "tax_kfb_tu"]])
    return ts[
        ["tax_{}".format(inc) for inc in tb["zve_list"]]
        + ["tax_{}_tu".format(inc) for inc in tb["zve_list"]]
        + ["abgst_tu", "abgst", "soli", "soli_tu"]
    ]


def abgeltung(df, tb):
    """ Capital Income Tax / Abgeltungsteuer
        since 2009, captial income is taxed with a flatrate of 25%.
    """
    df_abgelt = pd.DataFrame(index=df.index.copy())
    df_abgelt["abgst"] = 0
    if tb["yr"] >= 2009:
        df_abgelt.loc[~df["zveranl"], "abgst"] = tb["abgst"] * np.maximum(
            df["gross_e5"] - tb["spsparf"] - tb["spwerbz"], 0
        )
        df_abgelt.loc[df["zveranl"], "abgst"] = (
            0.5
            * tb["abgst"]
            * np.maximum(df["gross_e5_tu"] - 2 * (tb["spsparf"] + tb["spwerbz"]), 0)
        )
    return df_abgelt["abgst"]


@np.vectorize
def tarif(x, tb):
    """ The German Income Tax Tariff
    modelled only after 2002 so far

    It's not calculated as in the tax code, but rather a gemoetric decomposition of the
    area beneath the marginal tax rate function.
    This facilitates the implementation of alternative tax schedules

    args:
        x (float): taxable income
        tb (dict): tax-benefit parameters specific to year and reform
    """
    if tb["yr"] < 2002:
        raise ValueError("Income Tax Pre 2002 not yet modelled!")
    else:
        t = 0.0
        if tb["G"] < x <= tb["M"]:
            t = (
                ((tb["t_m"] - tb["t_e"]) / (2 * (tb["M"] - tb["G"]))) * (x - tb["G"])
                + tb["t_e"]
            ) * (x - tb["G"])
        if tb["M"] < x <= tb["S"]:
            t = (
                ((tb["t_s"] - tb["t_m"]) / (2 * (tb["S"] - tb["M"]))) * (x - tb["M"])
                + tb["t_m"]
            ) * (x - tb["M"]) + (tb["M"] - tb["G"]) * ((tb["t_m"] + tb["t_e"]) / 2)
        if x > tb["S"]:
            t = (
                tb["t_s"] * x
                - tb["t_s"] * tb["S"]
                + ((tb["t_s"] + tb["t_m"]) / 2) * (tb["S"] - tb["M"])
                + ((tb["t_m"] + tb["t_e"]) / 2) * (tb["M"] - tb["G"])
            )
        if x > tb["R"]:
            t = t + (tb["t_r"] - tb["t_s"]) * (x - tb["R"])
        # round down to next integer
        # t = int(t)
        assert t >= 0
    return t


def soli_formula(solibasis, tb):
    """ The actual soli calculation

    args:
        solibasis: taxable income, *always with Kinderfreibetrag!*
        tb (dict): tax-benefit parameters

    """
    soli = np.minimum(
        tb["solisatz"] * solibasis,
        np.maximum(0.2 * (solibasis - tb["solifreigrenze"]), 0),
    )

    return soli


def favorability_check(df, tb, yr):
    """ 'Higher-Yield Tepst'
        compares the tax burden that results from various definitions of the tax base
        Most importantly, it compares the tax burden without applying the child
        allowance (_nokfb) AND receiving child benefit with the tax burden including
        the child allowance (_kfb), but without child benefit. The most beneficial (
        for the household) is chocen. If child allowance is claimed, kindergeld is
        set to zero A similar check applies to whether it is more profitable to
        tax capital incomes with the standard 25% rate or to include it in the tariff.
    """
    fc = pd.DataFrame(index=df.index.copy())
    fc["tu_id"] = df["tu_id"]
    fc["hid"] = df["hid"]
    fc["pid"] = df["pid"]
    fc["kindergeld"] = df["kindergeld_basis"]
    fc["kindergeld_tu"] = df["kindergeld_tu_basis"]
    if yr < 2009:
        inclist = ["nokfb", "kfb"]
    else:
        inclist = ["nokfb", "abg_nokfb", "kfb", "abg_kfb"]
    """
    df = df.sort_values(by=['hid', 'tu_id', 'pid'])
    df[['hid', 'tu_id', 'child', 'tax_nokfb_tu', 'tax_kfb_tu',
        'kindergeld_basis' ,'kindergeld_tu_basis']].to_excel('Z:/test/fav_check.xlsx')
    """
    for inc in inclist:
        # Nettax is defined on the maximum within the tax unit.
        # Reason: This way, kids get assigned the tax payments of their parents,
        # ensuring correct treatment afterwards
        fc["tax_" + inc + "_tu"] = df["tax_" + inc + "_tu"]
        fc = fc.join(
            fc.groupby(["tu_id"])["tax_" + inc + "_tu"].max(),
            on=["tu_id"],
            how="left",
            rsuffix="_max",
        )
        fc = fc.rename(columns={"tax_" + inc + "_tu_max": "nettax_" + inc})
        # for those tax bases without capital taxes in tariff,
        # add abgeltungssteuer
        if "abg" not in inc:
            fc["nettax_" + inc] = fc["nettax_" + inc] + df["abgst_tu"]
        # For those tax bases without kfb, subtract kindergeld.
        # Before 1996, both child allowance and child benefit could be claimed
        if ("nokfb" in inc) | (yr <= 1996):
            fc["nettax_" + inc] = fc["nettax_" + inc] - (12 * df["kindergeld_tu_basis"])
    # get the maximum income, i.e. the minimum payment burden
    fc["minpay"] = fc.filter(regex="nettax").min(axis=1)
    # relevant tax base. not really needed...
    # fc['tax_income'] = 0
    # relevant incometax associated with this tax base
    fc["incometax_tu"] = 0
    # secures that every tax unit gets 'treated'
    fc["abgehakt"] = False
    for inc in inclist:
        """
        fc.loc[(fc['minpay'] == fc['nettax_' + inc])
               & (~fc['abgehakt'])
               & (~df['child']),
               'tax_income'] = df['zve_'+inc]
        """
        # Income Tax in monthly terms! And write only to parents
        fc.loc[
            (fc["minpay"] == fc["nettax_" + inc]) & (~fc["abgehakt"]) & (~df["child"]),
            "incometax_tu",
        ] = (df["tax_" + inc + "_tu"] / 12)
        # set kindergeld to zero if necessary.
        if (not ("nokfb" in inc)) | (yr <= 1996):
            fc.loc[
                (fc["minpay"] == fc["nettax_" + inc]) & (~fc["abgehakt"]), "kindergeld"
            ] = 0
            fc.loc[
                (fc["minpay"] == fc["nettax_" + inc]) & (~fc["abgehakt"]),
                "kindergeld_tu",
            ] = 0
        if "abg" in inc:
            fc.loc[
                (fc["minpay"] == fc["nettax_" + inc]) & (~fc["abgehakt"]), "abgst"
            ] = 0
            fc.loc[
                (fc["minpay"] == fc["nettax_" + inc]) & (~fc["abgehakt"]), "abgst_tu"
            ] = 0
        fc.loc[(fc["minpay"] == fc["nettax_" + inc]), "abgehakt"] = True

    # Aggregate Child benefit on the household.
    fc["kindergeld_hh"] = fc["kindergeld"].sum()
    # Assign Income tax to individuals
    fc["incometax"] = np.select(
        [df["zveranl"], ~df["zveranl"]], [fc["incometax_tu"] / 2, fc["incometax_tu"]]
    )

    # Control output
    # df.to_excel(
    #     pd.ExcelWriter(data_path + "check_güsntiger.xlsx"),
    #     sheet_name="py_out",
    #     columns=[
    #         "tu_id",
    #         "child",
    #         "zveranl",
    #         "minpay",
    #         "incometax",
    #         "abgehakt",
    #         "nettax_abg_kfb_tu",
    #         "zve_abg_kfb_tu",
    #         "tax_abg_kfb_tu",
    #         "nettax_abg_kfb_tu",
    #         "zve_abg_kfb_tu",
    #         "tax_abg_kfb_tu",
    #         "nettax_abg_kfb_tu",
    #         "zve_abg_kfb_tu",
    #         "tax_abg_kfb_tu",
    #         "nettax_abg_kfb_tu",
    #         "zve_abg_kfb_tu",
    #         "tax_abg_kfb_tu",
    #     ],
    #     na_rep="NaN",
    #     freeze_panes=(0, 1),
    # )
    # pd.to_pickle(df, data_path + ref + "/taxben_check")
    # df.to_excel(
    #     pd.ExcelWriter(data_path + "check_tax_incomes.xlsx"),
    #     sheet_name="py_out",
    #     columns=[
    #         "hid",
    #         "pid",
    #         "age",
    #         "female",
    #         "child",
    #         "zve_nokfb",
    #         "zve_kfb",
    #         "tax_nokfb",
    #         "tax_kfb",
    #         "gross_e1",
    #         "gross_e4",
    #         "gross_e5",
    #         "gross_e6",
    #         "gross_e7",
    #         "gross_gde",
    #     ],
    #     na_rep="NaN",
    #     freeze_panes=(0, 1),
    # )
    return fc[
        [
            "hid",
            "pid",
            "incometax_tu",
            "incometax",
            "kindergeld",
            "kindergeld_hh",
            "kindergeld_tu",
        ]
    ]


def kindergeld(df, tb):
    """ Child Benefit (kindergeld)
    Basic Amount for each child. Parents receive child benefit for every child up to 18 years.
    Above, they get it only up to tb["kgage"] if the child is
    a) in eduacation and
    b) not working too much / not receiving too much income (depending on the year)

    Returns:
        pd.series:
            kindergeld_basis: Kindergeld on the individual level
            kindergeld_tu_basis: Kindergeld summed up within the tax unit
    """
    kg = pd.DataFrame(index=df.index.copy())
    kg["tu_id"] = df["tu_id"]

    kg["child_count"] = tb["childben_elig_rule"](df, tb).cumsum()

    kg_amounts = {1: tb["kgeld1"], 2: tb["kgeld2"], 3: tb["kgeld3"], 4: tb["kgeld4"]}
    kg["kindergeld_basis"] = kg["child_count"].replace(kg_amounts)
    kg.loc[kg["child_count"] > 4, "kindergeld_basis"] = tb["kgeld4"]
    kg["kindergeld_tu_basis"] = kg.groupby("tu_id")["kindergeld_basis"].transform(sum)

    return kg[["kindergeld_basis", "kindergeld_tu_basis"]]


def kg_eligibility_hours(df, tb):
    """ Nowadays, kids must not work more than 20 hour
    """
    df = df.copy()
    df["eligible"] = df["age"] <= 18
    df.loc[
        (df["age"].between(19, tb["kgage"]))
        & df["ineducation"]
        & (df["w_hours"] <= 20),
        "eligible",
    ] = True

    return df["eligible"]


def kg_eligibility_wage(df, tb):
    """ Before 2011, there was an income ceiling for children
    """
    df = df.copy()
    df["eligible"] = df["age"] <= 18
    df.loc[
        (df["age"].between(19, tb["kgage"]))
        & df["ineducation"]
        & (df["m_wage"] <= tb["kgfreib"] / 12),
        "eligible",
    ] = True

    return df["eligible"]
