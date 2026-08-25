NAME_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}
ABBREV_LEN = 3


def split_tokens(full_name):
    tokens = str(full_name or "").split()
    while tokens and tokens[-1].rstrip(".").casefold() in NAME_SUFFIXES:
        tokens.pop()
    return tokens


def split_driver_name(full_name):
    tokens = split_tokens(full_name)
    if not tokens:
        return "", "", str(full_name or ""), ""
    last_name = tokens[-1]
    first_name = " ".join(tokens[:-1])
    abbreviation = last_name[:ABBREV_LEN].upper()
    return first_name, last_name, str(full_name).strip(), abbreviation
