from setuptools import find_packages, setup
import os

def get_requirements():
    reqs_path = os.path.join(
        os.path.dirname(__file__),
        'requirements.txt'
    )
    with open(reqs_path, 'r') as f:
        reqs = [
            r.strip() for r in f
            if r.strip()
        ]
    return reqs


setup(
    name='netbox_agent',
    version='1.0.0',
    description='NetBox agent for server',
    long_description=open('README.md', encoding="utf-8").read(),
    long_description_content_type='text/markdown',
    url='https://github.com/solvik/netbox_agent',
    author='Solvik Blum',
    author_email='solvik@solvik.fr',
    license='Apache2',
    include_package_data=True,
    packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    use_scm_version=True,
    install_requires=get_requirements(),
    zip_safe=False,
    keywords=['netbox'],
    classifiers=[
        'Intended Audience :: Developers',
        'Development Status :: 5 - Production/Stable',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
    ],
    entry_points={
        'console_scripts': ['netbox_agent=netbox_agent.cli:main'],
    }
)
