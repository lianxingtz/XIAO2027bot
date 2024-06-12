try:
    import solana
    print("solana module contents:", dir(solana))
except ImportError as e:
    print(f"Error importing solana: {e}")
