from setuptools import find_packages, setup

setup(
    name='netbox_agent',
    version='0.6.2',
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
    install_requires=[
        'pynetbox==5.0.5',
        'netaddr==0.8.0',
        'netifaces==0.10.9',
        'pyyaml==5.4.1',
        'jsonargparse==2.32.2',
    ],
    zip_safe=False,
    keywords=['netbox'],
    classifiers=[
        'Intended Audience :: Developers',
        'Development Status :: 5 - Production/Stable',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
    entry_points={
        'console_scripts': ['netbox_agent=netbox_agent.cli:main'],
    }
)
