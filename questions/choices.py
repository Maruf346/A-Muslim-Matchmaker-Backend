"""
questions/choices.py

All choice constants used across MaleBasicInfo, FemaleBasicInfo,
WaliBasicInfo, and WaliProfile models.

Kept in one file to avoid duplication — Male, Female and Wali share
most of the same lists (ethnicity, nationality, height, weight, etc.).
"""


# ─────────────────────────────────────────────────────────────────────────────
# How did you find us?
# ─────────────────────────────────────────────────────────────────────────────

HOW_FOUND_CHOICES = [
    ("referral",             "By Referral"),
    ("instagram",            "Instagram"),
    ("faiyad_fit",           "FaiyadFit"),
    ("youtube",              "Youtube"),
    ("a_muslim_homemaker",   "A Muslim Homemaker"),
    ("iron_fit_coaching",    "IronFitCoaching"),
    ("a_muslim_guide",       "A Muslim Guide"),
    ("facebook",             "Facebook"),
    ("other",                "Other"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Religion / Sect
# ─────────────────────────────────────────────────────────────────────────────

SECT_CHOICES = [
    ("sunni",  "Sunni"),
    ("salafi", "Sunni/Salafi"),
    ("other",  "Other Sect"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Marital Status
# ─────────────────────────────────────────────────────────────────────────────

MARITAL_STATUS_CHOICES = [
    ("never_married", "Never been married"),
    ("polygyny",      "Married (Polygyny)"),
    ("khula",         "Annulment (Khula)"),
    ("divorced",      "Divorced"),
    ("widowed",       "Widowed"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Ethnicity  (shared — male, female, wali)
# ─────────────────────────────────────────────────────────────────────────────

ETHNICITY_CHOICES = [
    ("afghan", "Afghan"), ("african_american", "African-American"), ("albanian", "Albanian"),
    ("algerian", "Algerian"), ("american", "American"), ("andorran", "Andorran"),
    ("angolan", "Ango"), ("anguillan", "Anguillan"), ("antiguan", "Antigua"),
    ("argentine", "Argentine"), ("armenian", "Armenian"), ("australian", "Australian"),
    ("austrian", "Austrian"), ("azerbaijani", "Azerbaijani"), ("bahamian", "Bahamian"),
    ("bahraini", "Bahraini"), ("bangladeshi", "Bangladeshi"), ("barbadian", "Barbadian"),
    ("belarusian", "Belarusian"), ("belgian", "Belgian"), ("belizean", "Belizean"),
    ("beninese", "Beninese"), ("bermudian", "Bermudian"), ("bhutanese", "Bhutanese"),
    ("black", "Black"), ("bolivian", "Bolivian"), ("bosnian", "Bosnian"),
    ("botswanan", "Botswanan"), ("brazilian", "Brazilian"), ("british", "British"),
    ("british_vi", "British Virgin Islander"), ("bruneian", "Bruneian"),
    ("bulgarian", "Bulgarian"), ("burkinan", "Burkinan"), ("burmese", "Burmese"),
    ("burundian", "Burundian"), ("cambodian", "Cambodian"), ("cameroonian", "Cameroonian"),
    ("canadian", "Canadian"), ("cape_verdean", "Cape Verdean"), ("cayman_islander", "Cayman Islander"),
    ("central_african", "Central African"), ("chadian", "Chadian"), ("chilean", "Chilean"),
    ("chinese", "Chinese"), ("colombian", "Colombian"), ("comoran", "Comoran"),
    ("congolese_rep", "Congolese (Congo)"), ("congolese_drc", "Congolese (DRC)"),
    ("cook_islander", "Cook Islander"), ("costa_rican", "Costa Rican"), ("croatian", "Croatian"),
    ("cuban", "Cuban"), ("cymraes", "Cymraes"), ("cymro", "Cymro"), ("cypriot", "Cypriot"),
    ("czech", "Czech"), ("danish", "Danish"), ("djiboutian", "Djiboutian"),
    ("dominican", "Dominican"), ("dominican_rep", "Citizen of the Dominican Republic"),
    ("dutch", "Dutch"), ("east_timorese", "East Timorese"), ("ecuadorean", "Ecuadorean"),
    ("egyptian", "Egyptian"), ("emirati", "Emirati"), ("equatorial_guinean", "Equatorial Guinean"),
    ("eritrean", "Eritrean"), ("estonian", "Estonian"), ("ethiopian", "Ethiopian"),
    ("faroese", "Faroese"), ("fijian", "Fijian"), ("filipino", "Filipino"),
    ("finnish", "Finnish"), ("french", "French"), ("gabonese", "Gabonese"),
    ("gambian", "Gambian"), ("georgian", "Georgian"), ("german", "German"),
    ("ghanaian", "Ghanaian"), ("gibraltarian", "Gibraltarian"), ("greek", "Greek"),
    ("greenlandic", "Greenlandic"), ("grenadian", "Grenadian"), ("guamanian", "Guamanian"),
    ("guatemalan", "Guatemalan"), ("guinea_bissau", "Citizen of Guinea-Bissau"),
    ("guinean", "Guinean"), ("guyanese", "Guyanese"), ("haitian", "Haitian"),
    ("honduran", "Honduran"), ("hong_konger", "Hong Konger"), ("hungarian", "Hungarian"),
    ("icelandic", "Icelandic"), ("indian", "Indian"), ("indonesian", "Indonesian"),
    ("iranian", "Iranian"), ("iraqi", "Iraqi"), ("irish", "Irish"), ("italian", "Italian"),
    ("ivorian", "Ivorian"), ("jamaican", "Jamaican"), ("japanese", "Japanese"),
    ("jordanian", "Jordanian"), ("kashmiri", "Kashmiri"), ("kazakh", "Kazakh"),
    ("kenyan", "Kenyan"), ("kittitian", "Kittitian"), ("kiribati", "Citizen of Kiribati"),
    ("kosovan", "Kosovan"), ("kurdish", "Kurdish"), ("kuwaiti", "Kuwaiti"),
    ("kyrgyz", "Kyrgyz"), ("lao", "Lao"), ("latvian", "Latvian"), ("lebanese", "Lebanese"),
    ("liberian", "Liberian"), ("libyan", "Libyan"), ("liechtenstein", "Liechtenstein citizen"),
    ("lithuanian", "Lithuanian"), ("luxembourger", "Luxembourger"), ("macanese", "Macanese"),
    ("macedonian", "Macedonian"), ("malagasy", "Malagasy"), ("malawian", "Malawian"),
    ("malaysian", "Malaysian"), ("maldivian", "Maldivian"), ("malian", "Malian"),
    ("maltese", "Maltese"), ("marshallese", "Marshallese"), ("martiniquais", "Martiniquais"),
    ("mauritanian", "Mauritanian"), ("mauritian", "Mauritian"), ("mexican", "Mexican"),
    ("micronesian", "Micronesian"), ("mixed_race", "Mixed Race"), ("moldovan", "Moldovan"),
    ("monegasque", "Monegasque"), ("mongolian", "Mongolian"), ("montenegrin", "Montenegrin"),
    ("montserratian", "Montserratian"), ("moroccan", "Moroccan"), ("mosotho", "Mosotho"),
    ("mozambican", "Mozambican"), ("namibian", "Namibian"), ("nauruan", "Nauruan"),
    ("nepalese", "Nepalese"), ("new_zealander", "New Zealander"), ("nicaraguan", "Nicaraguan"),
    ("nigerian", "Nigerian"), ("nigerien", "Nigerien"), ("niuean", "Niuean"),
    ("north_korean", "North Korean"), ("northern_irish", "Northern Irish"),
    ("norwegian", "Norwegian"), ("omani", "Omani"), ("pakistani", "Pakistani"),
    ("palauan", "Palauan"), ("palestinian", "Palestinian"), ("panamanian", "Panamanian"),
    ("papua_new_guinean", "Papua New Guinean"), ("paraguayan", "Paraguayan"),
    ("peruvian", "Peruvian"), ("pitcairn_islander", "Pitcairn Islander"),
    ("polish", "Polish"), ("portuguese", "Portuguese"), ("prydeinig", "Prydeinig"),
    ("puerto_rican", "Puerto Rican"), ("qatari", "Qatari"), ("romanian", "Romanian"),
    ("russian", "Russian"), ("rwandan", "Rwandan"), ("salvadorean", "Salvadorean"),
    ("sammarinese", "Sammarinese"), ("samoan", "Samoan"), ("sao_tomean", "Sao Tomean"),
    ("saudi_arabian", "Saudi Arabian"), ("scottish", "Scottish"), ("senegalese", "Senegalese"),
    ("serbian", "Serbian"), ("seychellois", "Seychelles"), ("sierra_leonean", "Sierra Leonean"),
    ("singaporean", "Singaporean"), ("slovak", "Slovak"), ("slovenian", "Slovenian"),
    ("solomon_islander", "Solomon Islander"), ("somali", "Somali"),
    ("south_african", "South African"), ("south_korean", "South Korean"),
    ("south_sudanese", "South Sudanese"), ("spanish", "Spanish"), ("sri_lankan", "Sri Lankan"),
    ("st_helenian", "St Helenian"), ("st_lucian", "St Lucian"), ("sudanese", "Sudanese"),
    ("surinamese", "Surinamese"), ("swazi", "Swazi"), ("swedish", "Swedish"),
    ("swiss", "Swiss"), ("syrian", "Syrian"), ("taiwanese", "Taiwanese"),
    ("tajik", "Tajik"), ("tanzanian", "Tanzanian"), ("thai", "Thai"),
    ("togolese", "Togolese"), ("tongan", "Tongan"), ("trinidadian", "Trinidadian"),
    ("tristanian", "Tristanian"), ("tunisian", "Tunisian"), ("turkish", "Turkish"),
    ("turkmen", "Turkmen"), ("turks_caicos", "Turks and Caicos Islander"),
    ("tuvaluan", "Tuvaluan"), ("ugandan", "Ugandan"), ("ukrainian", "Ukrainian"),
    ("uruguayan", "Uruguayan"), ("uzbek", "Uzbek"), ("vatican", "Vatican citizen"),
    ("vanuatu", "Citizen of Vanuatu"), ("venezuelan", "Venezuelan"),
    ("vietnamese", "Vietnamese"), ("vincentian", "Vincentian"), ("wallisian", "Wallisian"),
    ("welsh", "Welsh"), ("white", "White"), ("yemeni", "Yemeni"),
    ("zambian", "Zambian"), ("zimbabwean", "Zimbabwean"),
    ("other", "Other"), ("open_other", "Open to other Ethnicities"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Nationality / Citizenship  (same list minus a few ethnicity-only entries)
# ─────────────────────────────────────────────────────────────────────────────

NATIONALITY_CHOICES = [
    ("afghan", "Afghan"), ("albanian", "Albanian"), ("algerian", "Algerian"),
    ("american", "American"), ("andorran", "Andorran"), ("angolan", "Ango"),
    ("anguillan", "Anguillan"), ("antiguan", "Antigua"), ("argentine", "Argentine"),
    ("armenian", "Armenian"), ("australian", "Australian"), ("austrian", "Austrian"),
    ("azerbaijani", "Azerbaijani"), ("bahamian", "Bahamian"), ("bahraini", "Bahraini"),
    ("bangladeshi", "Bangladeshi"), ("barbadian", "Barbadian"), ("belarusian", "Belarusian"),
    ("belgian", "Belgian"), ("belizean", "Belizean"), ("beninese", "Beninese"),
    ("bermudian", "Bermudian"), ("bhutanese", "Bhutanese"), ("bolivian", "Bolivian"),
    ("bosnian", "Bosnian"), ("botswanan", "Botswanan"), ("brazilian", "Brazilian"),
    ("british", "British"), ("british_vi", "British Virgin Islander"), ("bruneian", "Bruneian"),
    ("bulgarian", "Bulgarian"), ("burkinan", "Burkinan"), ("burmese", "Burmese"),
    ("burundian", "Burundian"), ("cambodian", "Cambodian"), ("cameroonian", "Cameroonian"),
    ("canadian", "Canadian"), ("cape_verdean", "Cape Verdean"), ("cayman_islander", "Cayman Islander"),
    ("central_african", "Central African"), ("chadian", "Chadian"), ("chilean", "Chilean"),
    ("chinese", "Chinese"), ("colombian", "Colombian"), ("comoran", "Comoran"),
    ("congolese_rep", "Congolese (Congo)"), ("congolese_drc", "Congolese (DRC)"),
    ("cook_islander", "Cook Islander"), ("costa_rican", "Costa Rican"), ("croatian", "Croatian"),
    ("cuban", "Cuban"), ("cymraes", "Cymraes"), ("cymro", "Cymro"), ("cypriot", "Cypriot"),
    ("czech", "Czech"), ("danish", "Danish"), ("djiboutian", "Djiboutian"),
    ("dominican", "Dominican"), ("dominican_rep", "Citizen of the Dominican Republic"),
    ("dutch", "Dutch"), ("east_timorese", "East Timorese"), ("ecuadorean", "Ecuadorean"),
    ("egyptian", "Egyptian"), ("emirati", "Emirati"), ("equatorial_guinean", "Equatorial Guinean"),
    ("eritrean", "Eritrean"), ("estonian", "Estonian"), ("ethiopian", "Ethiopian"),
    ("faroese", "Faroese"), ("fijian", "Fijian"), ("filipino", "Filipino"),
    ("finnish", "Finnish"), ("french", "French"), ("gabonese", "Gabonese"),
    ("gambian", "Gambian"), ("georgian", "Georgian"), ("german", "German"),
    ("ghanaian", "Ghanaian"), ("gibraltarian", "Gibraltarian"), ("greek", "Greek"),
    ("greenlandic", "Greenlandic"), ("grenadian", "Grenadian"), ("guamanian", "Guamanian"),
    ("guatemalan", "Guatemalan"), ("guinea_bissau", "Citizen of Guinea-Bissau"),
    ("guinean", "Guinean"), ("guyanese", "Guyanese"), ("haitian", "Haitian"),
    ("honduran", "Honduran"), ("hong_konger", "Hong Konger"), ("hungarian", "Hungarian"),
    ("icelandic", "Icelandic"), ("indian", "Indian"), ("indonesian", "Indonesian"),
    ("iranian", "Iranian"), ("iraqi", "Iraqi"), ("irish", "Irish"), ("italian", "Italian"),
    ("ivorian", "Ivorian"), ("jamaican", "Jamaican"), ("japanese", "Japanese"),
    ("jordanian", "Jordanian"), ("kazakh", "Kazakh"), ("kenyan", "Kenyan"),
    ("kittitian", "Kittitian"), ("kiribati", "Citizen of Kiribati"), ("kosovan", "Kosovan"),
    ("kurdish", "Kurdish"), ("kuwaiti", "Kuwaiti"), ("kyrgyz", "Kyrgyz"), ("lao", "Lao"),
    ("latvian", "Latvian"), ("lebanese", "Lebanese"), ("liberian", "Liberian"),
    ("libyan", "Libyan"), ("liechtenstein", "Liechtenstein citizen"), ("lithuanian", "Lithuanian"),
    ("luxembourger", "Luxembourger"), ("macanese", "Macanese"), ("macedonian", "Macedonian"),
    ("malagasy", "Malagasy"), ("malawian", "Malawian"), ("malaysian", "Malaysian"),
    ("maldivian", "Maldivian"), ("malian", "Malian"), ("maltese", "Maltese"),
    ("marshallese", "Marshallese"), ("martiniquais", "Martiniquais"), ("mauritanian", "Mauritanian"),
    ("mauritian", "Mauritian"), ("mexican", "Mexican"), ("micronesian", "Micronesian"),
    ("moldovan", "Moldovan"), ("monegasque", "Monegasque"), ("mongolian", "Mongolian"),
    ("montenegrin", "Montenegrin"), ("montserratian", "Montserratian"), ("moroccan", "Moroccan"),
    ("mosotho", "Mosotho"), ("mozambican", "Mozambican"), ("namibian", "Namibian"),
    ("nauruan", "Nauruan"), ("nepalese", "Nepalese"), ("new_zealander", "New Zealander"),
    ("nicaraguan", "Nicaraguan"), ("nigerian", "Nigerian"), ("nigerien", "Nigerien"),
    ("niuean", "Niuean"), ("north_korean", "North Korean"), ("northern_irish", "Northern Irish"),
    ("norwegian", "Norwegian"), ("omani", "Omani"), ("pakistani", "Pakistani"),
    ("palauan", "Palauan"), ("palestinian", "Palestinian"), ("panamanian", "Panamanian"),
    ("papua_new_guinean", "Papua New Guinean"), ("paraguayan", "Paraguayan"),
    ("peruvian", "Peruvian"), ("pitcairn_islander", "Pitcairn Islander"),
    ("polish", "Polish"), ("portuguese", "Portuguese"), ("prydeinig", "Prydeinig"),
    ("puerto_rican", "Puerto Rican"), ("qatari", "Qatari"), ("romanian", "Romanian"),
    ("russian", "Russian"), ("rwandan", "Rwandan"), ("salvadorean", "Salvadorean"),
    ("sammarinese", "Sammarinese"), ("samoan", "Samoan"), ("sao_tomean", "Sao Tomean"),
    ("saudi_arabian", "Saudi Arabian"), ("scottish", "Scottish"), ("senegalese", "Senegalese"),
    ("serbian", "Serbian"), ("seychellois", "Seychelles"), ("sierra_leonean", "Sierra Leonean"),
    ("singaporean", "Singaporean"), ("slovak", "Slovak"), ("slovenian", "Slovenian"),
    ("solomon_islander", "Solomon Islander"), ("somali", "Somali"),
    ("south_african", "South African"), ("south_korean", "South Korean"),
    ("south_sudanese", "South Sudanese"), ("spanish", "Spanish"), ("sri_lankan", "Sri Lankan"),
    ("st_helenian", "St Helenian"), ("st_lucian", "St Lucian"), ("sudanese", "Sudanese"),
    ("surinamese", "Surinamese"), ("swazi", "Swazi"), ("swedish", "Swedish"),
    ("swiss", "Swiss"), ("syrian", "Syrian"), ("taiwanese", "Taiwanese"),
    ("tajik", "Tajik"), ("tanzanian", "Tanzanian"), ("thai", "Thai"),
    ("togolese", "Togolese"), ("tongan", "Tongan"), ("trinidadian", "Trinidadian"),
    ("tristanian", "Tristanian"), ("tunisian", "Tunisian"), ("turkish", "Turkish"),
    ("turkmen", "Turkmen"), ("turks_caicos", "Turks and Caicos Islander"),
    ("tuvaluan", "Tuvaluan"), ("ugandan", "Ugandan"), ("ukrainian", "Ukrainian"),
    ("uruguayan", "Uruguayan"), ("uzbek", "Uzbek"), ("vatican", "Vatican citizen"),
    ("vanuatu", "Citizen of Vanuatu"), ("venezuelan", "Venezuelan"),
    ("vietnamese", "Vietnamese"), ("vincentian", "Vincentian"), ("wallisian", "Wallisian"),
    ("welsh", "Welsh"), ("yemeni", "Yemeni"), ("zambian", "Zambian"), ("zimbabwean", "Zimbabwean"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Children count
# ─────────────────────────────────────────────────────────────────────────────

CHILDREN_COUNT_CHOICES = [
    ("0",    "None"),
    ("1",    "1"),
    ("2",    "2"),
    ("3",    "3"),
    ("4",    "4"),
    ("5_plus", "5+"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Height — Male range: 121cm–215cm  |  Female/Wali range: 91cm–238cm
# Stored as the full display string e.g. "170cm - 5' 7\""
# ─────────────────────────────────────────────────────────────────────────────

# Helper to build height choices from a list of (cm, feet, inches) tuples
def _build_height_choices(entries):
    return [(f"{cm}cm - {ft}' {inch}\"", f"{cm}cm - {ft}' {inch}\"") for cm, ft, inch in entries]


# Male heights: 121cm – 215cm
_MALE_HEIGHT_RAW = [
    (121,4,0),(122,4,0),(123,4,0),(124,4,1),(125,4,1),(126,4,2),(127,4,2),(128,4,2),
    (129,4,3),(130,4,3),(131,4,4),(132,4,4),(133,4,4),(134,4,5),(135,4,5),(136,4,6),
    (137,4,6),(138,4,6),(139,4,7),(140,4,7),(141,4,8),(142,4,8),(143,4,8),(144,4,9),
    (145,4,9),(146,4,9),(147,4,10),(148,4,10),(149,4,11),(150,4,11),(151,4,11),
    (152,5,0),(153,5,0),(154,5,1),(155,5,1),(156,5,1),(157,5,2),(158,5,2),(159,5,3),
    (160,5,3),(161,5,3),(162,5,4),(163,5,4),(164,5,5),(165,5,5),(166,5,5),(167,5,6),
    (168,5,6),(169,5,7),(170,5,7),(171,5,7),(172,5,8),(173,5,8),(174,5,9),(175,5,9),
    (176,5,9),(177,5,10),(178,5,10),(179,5,10),(180,5,11),(181,5,11),(182,6,0),
    (183,6,0),(184,6,0),(185,6,1),(186,6,1),(187,6,2),(188,6,2),(189,6,2),(190,6,3),
    (191,6,3),(192,6,4),(193,6,4),(194,6,4),(195,6,5),(196,6,5),(197,6,6),(198,6,6),
    (199,6,6),(200,6,7),(201,6,7),(202,6,8),(203,6,8),(204,6,8),(205,6,9),(206,6,9),
    (207,6,9),(208,6,10),(209,6,10),(210,6,11),(211,6,11),(212,6,11),(213,7,0),
    (214,7,0),(215,7,1),
]

# Female/Wali heights: 91cm – 238cm
_FEMALE_HEIGHT_RAW = [
    (91,3,0),(92,3,0),(93,3,1),(94,3,1),(95,3,1),(96,3,2),(97,3,2),(98,3,3),(99,3,3),
    (100,3,3),(101,3,4),(102,3,4),(103,3,5),(104,3,5),(105,3,5),(106,3,6),(107,3,6),
    (108,3,7),(109,3,7),(110,3,7),(111,3,8),(112,3,8),(113,3,8),(114,3,9),(115,3,9),
    (116,3,10),(117,3,10),(118,3,10),(119,3,11),(120,3,11),(121,4,0),(122,4,0),(123,4,0),
    (124,4,1),(125,4,1),(126,4,2),(127,4,2),(128,4,2),(129,4,3),(130,4,3),(131,4,4),
    (132,4,4),(133,4,4),(134,4,5),(135,4,5),(136,4,6),(137,4,6),(138,4,6),(139,4,7),
    (140,4,7),(141,4,8),(142,4,8),(143,4,8),(144,4,9),(145,4,9),(146,4,9),(147,4,10),
    (148,4,10),(149,4,11),(150,4,11),(151,4,11),(152,5,0),(153,5,0),(154,5,1),(155,5,1),
    (156,5,1),(157,5,2),(158,5,2),(159,5,3),(160,5,3),(161,5,3),(162,5,4),(163,5,4),
    (164,5,5),(165,5,5),(166,5,5),(167,5,6),(168,5,6),(169,5,7),(170,5,7),(171,5,7),
    (172,5,8),(173,5,8),(174,5,9),(175,5,9),(176,5,9),(177,5,10),(178,5,10),(179,5,10),
    (180,5,11),(181,5,11),(182,6,0),(183,6,0),(184,6,0),(185,6,1),(186,6,1),(187,6,2),
    (188,6,2),(189,6,2),(190,6,3),(191,6,3),(192,6,4),(193,6,4),(194,6,4),(195,6,5),
    (196,6,5),(197,6,6),(198,6,6),(199,6,6),(200,6,7),(201,6,7),(202,6,8),(203,6,8),
    (204,6,8),(205,6,9),(206,6,9),(207,6,9),(208,6,10),(209,6,10),(210,6,11),(211,6,11),
    (212,6,11),(213,7,0),(214,7,0),(215,7,1),(216,7,1),(217,7,1),(218,7,2),(219,7,2),
    (220,7,3),(221,7,3),(222,7,3),(223,7,4),(224,7,4),(225,7,5),(226,7,5),(227,7,5),
    (228,7,6),(229,7,6),(230,7,7),(231,7,7),(232,7,7),(233,7,8),(234,7,8),(235,7,9),
    (236,7,9),(237,7,9),(238,7,10),
]

MALE_HEIGHT_CHOICES   = _build_height_choices(_MALE_HEIGHT_RAW)
FEMALE_HEIGHT_CHOICES = _build_height_choices(_FEMALE_HEIGHT_RAW)


# ─────────────────────────────────────────────────────────────────────────────
# Weight
# Male range starts at 40kg | Female range starts at 20kg — both end at 149kg
# Stored as full display string e.g. "70kg - 154lbs"
# ─────────────────────────────────────────────────────────────────────────────

_WEIGHT_LBS = {
    20:44,21:46,22:48,23:50,24:52,25:55,26:57,27:59,28:61,29:63,
    30:66,31:68,32:70,33:72,34:74,35:77,36:79,37:81,38:83,39:85,
    40:88,41:90,42:92,43:94,44:97,45:99,46:101,47:103,48:105,49:108,
    50:110,51:112,52:114,53:116,54:119,55:121,56:123,57:125,58:127,59:130,
    60:132,61:134,62:136,63:138,64:141,65:143,66:145,67:147,68:149,69:152,
    70:154,71:156,72:158,73:160,74:163,75:165,76:167,77:169,78:171,79:174,
    80:176,81:178,82:180,83:182,84:185,85:187,86:189,87:191,88:194,89:196,
    90:198,91:200,92:202,93:205,94:207,95:209,96:211,97:213,98:216,99:218,
    100:220,101:222,102:224,103:227,104:229,105:231,106:233,107:235,108:238,109:240,
    110:242,111:244,112:246,113:249,114:251,115:253,116:255,117:257,118:260,119:262,
    120:264,121:266,122:268,123:271,124:273,125:275,126:277,127:279,128:282,129:284,
    130:286,131:288,132:291,133:293,134:295,135:297,136:299,137:302,138:304,139:306,
    140:308,141:310,142:313,143:315,144:317,145:319,146:321,147:324,148:326,149:328,
}

MALE_WEIGHT_CHOICES   = [(f"{kg}kg - {lbs}lbs", f"{kg}kg - {lbs}lbs") for kg, lbs in _WEIGHT_LBS.items() if kg >= 40]
FEMALE_WEIGHT_CHOICES = [(f"{kg}kg - {lbs}lbs", f"{kg}kg - {lbs}lbs") for kg, lbs in _WEIGHT_LBS.items()]


# ─────────────────────────────────────────────────────────────────────────────
# Pray 5x a day
# ─────────────────────────────────────────────────────────────────────────────

PRAY_CHOICES = [
    ("yes",    "Yes"),
    ("mostly", "Mostly"),
    ("no",     "No"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Relocation
# ─────────────────────────────────────────────────────────────────────────────

RELOCATION_CHOICES = [
    ("yes",         "Yes"),
    ("no",          "No"),
    ("maybe",       "Maybe (open for discussion)"),
    ("later",       "Not right now, but at a later time"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Dress style  (female / wali)
# ─────────────────────────────────────────────────────────────────────────────

DRESS_CHOICES = [
    ("no_hijab",       "No Hijab"),
    ("hijab_pants",    "Hijab and Pants"),
    ("hijab_abaya",    "Hijab and Abaya"),
    ("niqab",          "Niqab"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Preferred dress  (male preference for spouse)
# ─────────────────────────────────────────────────────────────────────────────

PREFERRED_DRESS_CHOICES = [
    ("no_hijab",    "No Hijab"),
    ("hijab_pants", "Hijab and pants"),
    ("hijab_abaya", "Hijab and Abaya"),
    ("niqab",       "Niqab"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Education Level
# ─────────────────────────────────────────────────────────────────────────────

EDUCATION_CHOICES = [
    ("high_school",  "High School Graduate"),
    ("associates",   "Associates Degree"),
    ("technical",    "Technical Degree"),
    ("college",      "College"),
    ("bachelors",    "Bachelors Degree"),
    ("masters",      "Masters Degree"),
    ("graduate",     "Graduate Degree"),
    ("jd_md_phd",    "J.D./M.D./PhD"),
    ("other",        "Other"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Income (GBP)
# ─────────────────────────────────────────────────────────────────────────────

INCOME_CHOICES = [
    ("0_12k",           "£0 - £12k"),
    ("12_20k",          "£12k - £20k"),
    ("20_50k",          "£20k - £50k"),
    ("50_100k",         "£50k - £100k"),
    ("100_300k",        "£100k - £300k"),
    ("300_500k",        "£300k - £500k"),
    ("500k_plus",       "£500k+"),
    ("rather_not_say",  "Would rather not share"),
    ("unemployed",      "Unemployed"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Body Frame
# ─────────────────────────────────────────────────────────────────────────────

FRAME_CHOICES = [
    ("petite",          "Petite"),
    ("slim",            "Slim"),
    ("average",         "Average"),
    ("fit_athletic",    "Fit/Athletic"),
    ("muscular",        "Muscular"),
    ("curvy",           "Curvy"),
    ("few_extra",       "A few Extra Pounds"),
    ("wider_frame",     "Wider frame"),
    ("bulky",           "Bulky"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Languages Spoken
# ─────────────────────────────────────────────────────────────────────────────

LANGUAGE_CHOICES = [
    ("arabic",      "Arabic"),
    ("english",     "English"),
    ("french",      "French"),
    ("spanish",     "Spanish"),
    ("urdu",        "Urdu"),
    ("hindi",       "Hindi"),
    ("bengali",     "Bengali"),
    ("turkish",     "Turkish"),
    ("hausa",       "Hausa"),
    ("swahili",     "Swahili"),
    ("malay",       "Malay"),
    ("indonesian",  "Indonesian"),
    ("somali",      "Somali"),
    ("persian",     "Persian/Farsi"),
    ("pashto",      "Pashto"),
    ("punjabi",     "Punjabi"),
    ("german",      "German"),
    ("portuguese",  "Portuguese"),
    ("russian",     "Russian"),
    ("chinese",     "Chinese (Mandarin)"),
    ("other",       "Other"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Wali relation to sister
# ─────────────────────────────────────────────────────────────────────────────

WALI_RELATION_CHOICES = [
    ("father",      "Father"),
    ("brother",     "Brother"),
    ("uncle",       "Uncle"),
    ("grandfather", "Grandfather"),
    ("other",       "Other"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Wali gender
# ─────────────────────────────────────────────────────────────────────────────

WALI_GENDER_CHOICES = [
    ("male",   "Male"),
    ("female", "Female"),
]
