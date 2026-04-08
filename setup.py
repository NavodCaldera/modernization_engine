from setuptools import setup

setup(
    name='modernize-cli',
    version='3.0',
    py_modules=['cli'],
    install_requires=[
        'Click',
    ],
    entry_points={
        'console_scripts': [
            'modernize = cli:modernize',
        ],
    },
)