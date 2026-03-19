"""
Installation Verification Script
Run this to ensure all dependencies are correctly installed.
"""

import sys

def test_imports():
    """Test that all required packages can be imported."""
    print("Testing package imports...")
    
    required_packages = {
        'streamlit': 'Streamlit',
        'pandas': 'Pandas',
        'numpy': 'NumPy',
        'scipy': 'SciPy',
        'openpyxl': 'OpenPyXL',
        'matplotlib': 'Matplotlib',
        'seaborn': 'Seaborn'
    }
    
    failed = []
    
    for package, name in required_packages.items():
        try:
            __import__(package)
            print(f"✓ {name}")
        except ImportError as e:
            print(f"✗ {name} - FAILED")
            failed.append(package)
    
    if failed:
        print(f"\n❌ Installation incomplete. Missing packages: {', '.join(failed)}")
        print("Run: pip install -r requirements.txt")
        return False
    else:
        print("\n✅ All packages installed successfully!")
        return True


def test_project_files():
    """Verify all project files exist."""
    print("\nTesting project files...")
    
    import os
    
    required_files = [
        'main.py',
        'engine.py',
        'optimizer.py',
        'requirements.txt',
        'README.md'
    ]
    
    failed = []
    
    for file in required_files:
        if os.path.exists(file):
            print(f"✓ {file}")
        else:
            print(f"✗ {file} - NOT FOUND")
            failed.append(file)
    
    if failed:
        print(f"\n❌ Missing files: {', '.join(failed)}")
        return False
    else:
        print("\n✅ All project files present!")
        return True


def test_basic_functionality():
    """Test basic functionality of core modules."""
    print("\nTesting basic functionality...")
    
    try:
        # Test engine import
        from engine import SupplyChainEngine
        print("✓ engine.py imports successfully")
        
        # Test optimizer import
        from optimizer import GeneticOptimizer, GAConfig, Chromosome
        print("✓ optimizer.py imports successfully")
        
        # Test NumPy and SciPy functions
        import numpy as np
        from scipy.stats import norm
        
        z = 1.65
        loss = norm.pdf(z) - z * (1 - norm.cdf(z))
        assert loss >= 0, "Normal loss function should be non-negative"
        print("✓ Normal loss function works correctly")
        
        # Test random seed
        np.random.seed(42)
        sample1 = np.random.random(10)
        np.random.seed(42)
        sample2 = np.random.random(10)
        assert np.allclose(sample1, sample2), "Random seed not working"
        print("✓ Random seed reproducibility verified")
        
        print("\n✅ All functionality tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Functionality test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("MEIO PROJECT - INSTALLATION VERIFICATION")
    print("=" * 60)
    print()
    
    results = []
    
    # Test imports
    results.append(test_imports())
    
    # Test files
    results.append(test_project_files())
    
    # Test functionality
    results.append(test_basic_functionality())
    
    # Summary
    print("\n" + "=" * 60)
    if all(results):
        print("🎉 SUCCESS! Installation verified.")
        print("\nYou can now run the application with:")
        print("    streamlit run main.py")
    else:
        print("⚠️  INCOMPLETE! Some tests failed.")
        print("Please review the errors above and fix any issues.")
    print("=" * 60)


if __name__ == "__main__":
    main()
