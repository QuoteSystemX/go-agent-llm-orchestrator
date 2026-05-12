import requests
import sys

def get_stonfi_pool(pool_address):
    """
    Fetches pool information from Ston.fi API.
    """
    url = f"https://api.ston.fi/v1/pools/{pool_address}"
    print(f"--- Querying Ston.fi Pool: {pool_address} ---")
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        pool = data.get('pool', {})
        token0 = pool.get('token0_address')
        token1 = pool.get('token1_address')
        reserve0 = pool.get('reserve0')
        reserve1 = pool.get('reserve1')
        
        print(f"✅ Pool Found: {pool.get('address')}")
        print(f"  Token 0: {token0}")
        print(f"  Token 1: {token1}")
        print(f"  Reserve 0: {reserve0}")
        print(f"  Reserve 1: {reserve1}")
        
    except Exception as e:
        print(f"❌ Error querying Ston.fi: {e}")

if __name__ == "__main__":
    # Default to a known pool if none provided (e.g., TON/USDT)
    addr = sys.argv[1] if len(sys.argv) > 1 else "EQC8v9_fL6qC_m7y_U_7_v_fL6qC_m7y_U_7_v_fL6qC_m7y" # Mock address for example
    get_stonfi_pool(addr)
