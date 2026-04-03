import hashlib

def test_variations():
    key = "Y4PFDw"
    txnid = "SUB00034-260402181338"
    amount = "2000.00"
    productinfo = "ITR"
    # Testing boopathi vs Boopathi
    first_lowercase = "boopathi"
    first_capital = "Boopathi"
    email = "prakash.venkatesan@alonioncapital.com"
    udf1 = "ITR-SUB-00034"
    salt = "eKoE70FdldqSFC0sgo0TouPKj68x9ee8"

    # Sequence: 16 pipes
    # key|txnid|amount|productinfo|firstname|email|udf1|udf2|udf3|udf4|udf5|udf6|udf7|udf8|udf9|udf10|SALT
    
    s_low = f"{key}|{txnid}|{amount}|{productinfo}|{first_lowercase}|{email}|{udf1}||||||||||{salt}"
    h_low = hashlib.sha512(s_low.encode()).hexdigest()
    
    s_cap = f"{key}|{txnid}|{amount}|{productinfo}|{first_capital}|{email}|{udf1}||||||||||{salt}"
    h_cap = hashlib.sha512(s_cap.encode()).hexdigest()

    print(f"Target Hash (PayU Expects): 963feb840bbe092b3ac8754ddf61a9a613889c908136cc2f20e82d1026035691682a31e6ee177dc7967dd2db7468a6a6a2bb32129aa5622ffd59503cb52b3d4")
    print(f"Hash (boopathi): {h_low}")
    print(f"Hash (Boopathi): {h_cap}")
    
    # Check if b37aba matches anything
    print(f"User Got Hash: b37aba7ffb2f94c51ec3964b9eec609ee98390d3d6924246f5fd7b1f853488656d264ed8e842fe0d10d4edd24167356b38c63973d1b0ea17d7d70491a072a367")

if __name__ == "__main__":
    test_variations()
