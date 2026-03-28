# test_redis.py

import redis
import sys

def test_redis_connection(host='localhost', port=6379, db=0):
    try:
        r = redis.Redis(
            host=host,
            port=port,
            db=db,
            socket_connect_timeout=3
        )
        
        # Test connection
        response = r.ping()
        if response:
            print(f"✅ Redis connected successfully to {host}:{port}")
            
            # Test set/get
            r.set('test_key', 'test_value')
            value = r.get('test_key')
            if value.decode() == 'test_value':
                print("✅ Redis set/get test passed")
            else:
                print("❌ Redis set/get test failed")
            
            # Cleanup
            r.delete('test_key')
            
            # Get Redis info
            info = r.info()
            print(f"📊 Redis version: {info.get('redis_version')}")
            print(f"📊 Used memory: {info.get('used_memory_human')}")
            
            return True
        else:
            print("❌ Redis ping failed")
            return False
            
    except redis.ConnectionError as e:
        print(f"❌ Redis connection error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    # Read connection params from command line or use defaults
    host = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 6379
    
    success = test_redis_connection(host, port)
    sys.exit(0 if success else 1)