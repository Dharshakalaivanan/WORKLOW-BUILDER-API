#!/usr/bin/env python3
"""
Test script to verify the workflow builder API integration
"""
import asyncio
import json
import sys
from app.services.workflow_executor import WorkflowExecutor
from app.services.ai_client import AIClient

def test_workflow_executor():
    """Test the workflow executor functionality"""
    print("Testing WorkflowExecutor...")
    
    # Sample workflow data
    nodes = [
        {
            "id": "conversation-1",
            "type": "custom",
            "position": {"x": 100, "y": 100},
            "data": {
                "label": "Start Conversation",
                "type": "Conversation",
                "prompt": "Hello! How can I help you today?"
            }
        },
        {
            "id": "call-1",
            "type": "custom", 
            "position": {"x": 300, "y": 100},
            "data": {
                "label": "Make Call",
                "type": "Call",
                "phoneNumber": "+1234567890",
                "callScript": "This is an automated call from our system."
            }
        },
        {
            "id": "end-1",
            "type": "custom",
            "position": {"x": 500, "y": 100},
            "data": {
                "label": "End Call",
                "type": "End Call"
            }
        }
    ]
    
    edges = [
        {"id": "conversation-1-call-1", "source": "conversation-1", "target": "call-1"},
        {"id": "call-1-end-1", "source": "call-1", "target": "end-1"}
    ]
    
    # Create executor
    executor = WorkflowExecutor(nodes, edges)
    
    # Test execution
    print("Starting workflow execution...")
    result = executor.start_execution()
    print(f"Start result: {result}")
    
    # Execute first node
    result = executor.execute_current_node("Hello, I need help")
    print(f"Conversation result: {result}")
    
    # Move to next node
    next_node = executor.move_to_next_node()
    print(f"Next node: {next_node}")
    
    # Execute call node
    result = executor.execute_current_node()
    print(f"Call result: {result}")
    
    # Move to end
    next_node = executor.move_to_next_node()
    print(f"Next node: {next_node}")
    
    # Execute end node
    result = executor.execute_current_node()
    print(f"End result: {result}")
    
    # Check status
    status = executor.get_execution_status()
    print(f"Final status: {status}")
    
    print("WorkflowExecutor test completed!\n")

async def test_ai_client():
    """Test the AI client functionality"""
    print("Testing AIClient...")
    
    ai = AIClient()
    
    # Test basic generation
    try:
        response = await ai.generate("Hello, can you help me create a workflow?")
        print(f"AI Response: {response}")
    except Exception as e:
        print(f"AI Client test failed (expected if no API key): {e}")
    
    print("AIClient test completed!\n")

def test_workflow_data_structure():
    """Test workflow data structure compatibility"""
    print("Testing workflow data structure...")
    
    # Test node structure
    sample_node = {
        "id": "test-node",
        "type": "custom",
        "position": {"x": 100, "y": 100},
        "data": {
            "label": "Test Node",
            "type": "Conversation",
            "prompt": "Test prompt"
        }
    }
    
    # Test edge structure
    sample_edge = {
        "id": "test-edge",
        "source": "node1",
        "target": "node2",
        "animated": True,
        "style": {"stroke": "#4f8cff"}
    }
    
    print(f"Sample node: {json.dumps(sample_node, indent=2)}")
    print(f"Sample edge: {json.dumps(sample_edge, indent=2)}")
    
    print("Data structure test completed!\n")

async def main():
    """Run all tests"""
    print("=== Workflow Builder Integration Tests ===\n")
    
    test_workflow_data_structure()
    test_workflow_executor()
    await test_ai_client()
    
    print("=== All tests completed ===")

if __name__ == "__main__":
    asyncio.run(main())
