import hashlib

def test_hash():
    key = "Y4PFDw"
    txnid = "SUB00034-260402171748"
    amount = "1000.00"
    productinfo = "ITR"
    firstname = "boopathi"
    email = "prakash.venkatesan@alonioncapital.com"
    udf1 = "ITR-SUB-00034"
    udf2 = ""
    udf3 = ""
    udf4 = ""
    udf5 = ""
    salt = "eKoE70FdldqSFC0sgo0TouPKj68x9ee8"

    # Reference sequence: 16 pipes
    # key(1)txnid(2)amount(3)prod(4)first(5)email(6)udf1(7)udf2(8)udf3(9)udf4(10)udf5(11)udf6(12)udf7(13)udf8(14)udf9(15)udf10(16)SALT
    
    hash_str = f"{key}|{txnid}|{amount}|{productinfo}|{firstname}|{email}|{udf1}|{udf2}|{udf3}|{udf4}|{udf5}||||||{salt}"
    
    print(f"Hash String: {hash_str}")
    print(f"Pipe count: {hash_str.count('|')}")
    
    result = hashlib.sha512(hash_str.encode('utf-8')).hexdigest()
    print(f"Calculated Hash: {result}")

if __name__ == "__main__":
    test_hash()
