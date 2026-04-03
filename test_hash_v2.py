import hashlib

def solve_it():
    key = "Y4PFDw"
    txnid = "SUB00034-260402171748"
    amount = "1000.00"
    productinfo = "ITR"
    firstname = "boopathi"
    email = "prakash.venkatesan@alonioncapital.com"
    udf1 = "ITR-SUB-00034"
    salt = "eKoE70FdldqSFC0sgo0TouPKj68x9ee8"

    # Variation 1: 16 pipes (11 empty slots after email, or 10 after udf1)
    # The screenshot says: udf1|udf2|udf3|udf4|udf5||||||SALT
    # That's 10 pipes after udf1.
    
    # Try different pipe counts after udf1
    for i in range(1, 15):
        pipes = "|" * i
        s = f"{key}|{txnid}|{amount}|{productinfo}|{firstname}|{email}|{udf1}{pipes}{salt}"
        h = hashlib.sha512(s.encode()).hexdigest()
        if h.startswith("17970a"):
            print(f"MATCH FOUND at {i} pipes!")
            print(f"String: {s}")
            print(f"Hash: {h}")
            return

    print("No match found with standard SHA-512")

solve_it()
