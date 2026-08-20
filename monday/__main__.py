#!/usr/bin/env python3
"""
Monday - Multi-AI Personal Operating System

Main entry point for running Monday from the command line.
"""

import sys
import argparse
from monday.core import MondayOrchestrator


def main():
    """Main entry point for Monday CLI."""
    parser = argparse.ArgumentParser(
        description='Monday - Multi-AI Personal Operating System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  monday "Create an app for managing my school timetable"
  monday "Research the best Kotlin tutorials"
  monday "Make a poster for my school event"
  monday "Open Chrome and search for Python tutorials"
  monday "Predict the next number in 2 4 8 16 32"
  python -m monday.jarvis        # Jarvis prediction console
        """
    )
    
    parser.add_argument(
        'input',
        nargs='?',
        help='Natural language input for Monday to process'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='Monday 0.1.0'
    )
    
    args = parser.parse_args()
    
    if not args.input:
        # Interactive mode
        print("Monday v0.1.0 - Multi-AI Personal Operating System")
        print("Type 'quit' or 'exit' to stop\n")
        
        orchestrator = MondayOrchestrator()
        
        while True:
            try:
                user_input = input("› ").strip()
                
                if user_input.lower() in ['quit', 'exit']:
                    print("Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                result = orchestrator.process(user_input)
                
                print(f"\nStatus: {result.status}")
                print(f"Time: {result.execution_time:.2f}s")
                
                if result.outputs:
                    print("\nOutputs:")
                    for task_id, output in result.outputs.items():
                        print(f"  {task_id}: {output}")
                
                if result.artifacts:
                    print(f"\nArtifacts: {len(result.artifacts)} generated")
                
                if result.errors:
                    print(f"\nErrors: {len(result.errors)}")
                    for error in result.errors:
                        print(f"  - {error}")
                
                if result.warnings:
                    print(f"\nWarnings: {len(result.warnings)}")
                    for warning in result.warnings:
                        print(f"  - {warning}")
                
                print()
                
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except EOFError:
                print("\nGoodbye!")
                break
    else:
        # Single command mode
        orchestrator = MondayOrchestrator()
        result = orchestrator.process(args.input)
        
        if args.verbose:
            print(f"Request ID: {result.request_id}")
            print(f"Input: {result.original_input}")
            print(f"Status: {result.status}")
            print(f"Execution Time: {result.execution_time:.2f}s")
            
            if result.task_graph:
                progress = result.task_graph.get_progress()
                print(f"\nTask Progress:")
                print(f"  Total: {progress['total']}")
                print(f"  Completed: {progress['completed']}")
                print(f"  Failed: {progress['failed']}")
                print(f"  Pending: {progress['pending']}")
            
            if result.model_usage:
                print(f"\nModel Usage: {result.model_usage}")
        else:
            print(f"Status: {result.status}")
            
            if result.errors:
                print(f"Errors: {', '.join(result.errors)}")
        
        # Exit with appropriate code
        sys.exit(0 if result.status == 'success' else 1)


if __name__ == '__main__':
    main()
