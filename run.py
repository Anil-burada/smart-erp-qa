"""Start the local dashboard on a loopback address only."""
import uvicorn

if __name__ == '__main__':
    print('Smart ERP QA local dashboard: http://127.0.0.1:8766')
    uvicorn.run('backend.api:app', host='127.0.0.1', port=8766, reload=False)
