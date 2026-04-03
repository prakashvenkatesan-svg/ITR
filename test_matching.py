def test_matching_logic():
    # Simulated numbers
    stored_numbers = ["9876543210", "98765 43210", "+91 98765 43210", "09876543210"]
    incoming_numbers = ["919876543210", "+919876543210", "9876543210"]

    print(f"{'Incoming':<15} | {'Stored':<15} | {'Match (Last 10)':<15}")
    print("-" * 50)
    
    for incoming in incoming_numbers:
        # Current logic: sender_number = str(raw_number).strip().replace("+", "")
        sender_number = incoming.strip().replace("+", "")
        last_10_incoming = sender_number[-10:]
        
        for stored in stored_numbers:
            # Current logic: mobile_number LIKE %{sender_number[-10:]}
            # This is equivalent to: stored.endswith(last_10_incoming)
            match = stored.endswith(last_10_incoming)
            print(f"{incoming:<15} | {stored:<15} | {str(match):<15}")

if __name__ == "__main__":
    test_matching_logic()
