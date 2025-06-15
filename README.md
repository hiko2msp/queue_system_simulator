# Data Lake on AWS with CDK

### Overview
This project demonstrates building a modern data lake on AWS using the AWS Cloud Development Kit (CDK) in TypeScript. The components include:
- **Amazon S3**: For storing raw and processed data, primarily in Parquet format.
- **Amazon Aurora MySQL**: As a relational data source for transactional or structured data.
- **Amazon Redshift Serverless**: As a data warehouse, enabling analytical queries.
- **AWS Glue Data Catalog**: For cataloging data from S3, making it discoverable.
- **AWS Lake Formation**: For centralized data access governance and fine-grained permissions.
- **Zero-ETL Integration**: Seamless data replication from Aurora MySQL to Redshift Serverless.
- **AWS IAM**: For defining roles and policies ensuring secure access between services.
- **Amazon QuickSight**: For business intelligence and visualization (manual setup guidance provided).

### Architecture Diagram (Placeholder)
`[Architecture Diagram - To be added]`

### Prerequisites
- An active AWS Account.
- AWS CLI configured with credentials that have permissions to deploy the resources defined in this stack. The CDK execution role (the one CloudFormation uses) will need broad permissions across services like S3, RDS, Redshift, Glue, Lake Formation, IAM, EC2, and Secrets Manager.
- Node.js (v18.x or later recommended) and npm installed.
- AWS CDK Toolkit installed globally: `npm install -g aws-cdk`.
- (Optional, for manual data loading) Sample Parquet files for S3.
- (Optional, for manual data loading) SQL scripts or client for loading data into Aurora MySQL.

### Project Structure
- `lib/app-stack.ts`: Contains the core CDK stack definition where all AWS resources are declared.
- `bin/app.ts`: The entry point for the CDK application, responsible for instantiating the stack.
- `cdk.json`: Configuration file for the CDK toolkit, specifying how to run the app and other context values.
- `package.json`: Defines project dependencies (CDK libraries, etc.) and scripts (build, deploy).
- `tsconfig.json`: TypeScript compiler options.

### Deployment Steps
1.  **Clone the Repository / Initialize Project**:
    If you have this project as a Git repository:
    ```bash
    git clone <repository-url>
    cd <repository-name>/app
    ```
    If starting from scratch, ensure you are in the `/app` directory where `cdk.json` is located.

2.  **Install Dependencies**:
    Navigate to the `/app` directory (if not already there) and install Node.js dependencies:
    ```bash
    npm install
    ```

3.  **Bootstrap CDK (if first time in the AWS Region/Account)**:
    If you haven't used CDK in this AWS account and region before, you need to bootstrap it. Replace `ACCOUNT-NUMBER` and `REGION` with your specific details.
    ```bash
    cdk bootstrap aws://ACCOUNT-NUMBER/REGION
    ```

4.  **Synthesize CloudFormation Template (Optional)**:
    To see the AWS CloudFormation template that CDK will generate:
    ```bash
    cdk synth
    ```

5.  **Deploy the Stack**:
    This command will provision all the AWS resources defined in the stack.
    ```bash
    cdk deploy
    ```
    Review the changes and confirm the deployment when prompted.

6.  **Note Stack Outputs**:
    After successful deployment, CDK will output several key values such as S3 bucket names, database endpoints, and IAM role ARNs. Save these, as they are needed for manual configuration and connection steps.

### Manual Configuration Steps

#### 1. Upload Sample Parquet Data to S3
- The stack creates an S3 bucket for raw data. Its name is available in the `S3BucketName` stack output.
- Upload your sample Parquet files to this bucket. For example, using AWS CLI:
  ```bash
  aws s3 cp /path/to/your/local/parquet_files/ s3://<S3BucketNameOutput>/your_data_prefix/ --recursive
  ```
- The Glue crawler (`GlueS3CrawlerName` output) is configured to crawl the root of this bucket. If you place data under prefixes, ensure the crawler path is set accordingly or update the crawler post-deployment if needed.

#### 2. Load Sample Data into Aurora MySQL
- Connect to the Aurora MySQL cluster:
    - **Endpoint**: Use the `AuroraClusterEndpoint` value from the stack outputs.
    - **Credentials**: The master username is `MasterUser` (or as defined). The password can be retrieved from AWS Secrets Manager using the `AuroraMasterUserSecretArn` output.
- Using your preferred SQL client, execute SQL commands to create a schema, tables, and insert data.
- Example SQL:
  ```sql
  -- Example:
  -- CREATE DATABASE IF NOT EXISTS mysampledb;
  -- USE mysampledb;

  CREATE TABLE IF NOT EXISTS customer_details (
    customer_id VARCHAR(255) PRIMARY KEY,
    customer_name VARCHAR(255),
    registration_date DATE
  );

  INSERT INTO customer_details (customer_id, customer_name, registration_date) VALUES
  ('cust101', 'Alice Wonderland', '2023-01-15'),
  ('cust102', 'Bob The Builder', '2023-02-20'),
  ('cust103', 'Charlie Chaplin', '2022-11-05');
  ```

#### 3. Verify Zero-ETL Integration
- Once Aurora contains data, the Zero-ETL integration should replicate it to Redshift Serverless.
- Connect to your Redshift Serverless workgroup (using `RedshiftWorkgroupName` output). The database name is `dev` (or as configured in `RedshiftNamespaceName`).
- You should find a new schema in Redshift named after the integration (check `AuroraRedshiftIntegrationArn` or `AuroraRedshiftIntegrationName` output for hints on the integration identifier).
- Within this schema, tables from your Aurora database (e.g., `customer_details`) should appear and be queryable.
  ```sql
  -- In Redshift, assuming the integration schema is something like 'aurora_integration_schema':
  -- SELECT * FROM aurora_integration_schema.customer_details LIMIT 10;
  ```

#### 4. Set up Lake Formation LF-Tags (Optional Best Practice)
This enhances data governance. These steps are typically done in the AWS Lake Formation console:
1.  **Define LF-Tag Keys**:
    - Example Keys: `Confidentiality`, `DataSource`, `PII` (Personally Identifiable Information).
2.  **Define Values for Keys**:
    - `Confidentiality`: `Low`, `Medium`, `High`
    - `DataSource`: `S3`, `Aurora`, `Redshift`
    - `PII`: `True`, `False`
3.  **Assign LF-Tags to Resources**:
    - **Glue Database**: Assign relevant tags (e.g., `DataSource:S3`).
    - **Glue Tables**: Assign tags to tables created by the crawler (e.g., `Confidentiality:Medium`, `PII:True` for specific tables).
    - **Table Columns**: Assign tags to specific columns within tables for fine-grained control.
    - **Redshift Resources**: If you are using Lake Formation to manage permissions for Redshift-native tables or views created on top of integrated data, you can assign LF-Tags there as well.
- Once tags are assigned, you can create LF-Tag-based access control (TBAC) policies to grant permissions to IAM roles (like `RedshiftDataLakeAccessRole` or `QuickSightAccessRoleArn`).

#### 5. Set up QuickSight
1.  **Ensure QuickSight User/Group Permissions**:
    - The QuickSight user or group performing the setup needs access to AWS services and specifically needs to be able to use the IAM role created for QuickSight (`QuickSightAccessRoleArn` output).
    - An QuickSight administrator might need to authorize this IAM role in QuickSight's "Manage QuickSight" -> "Security & permissions" -> "IAM role assignments".
2.  **Add New Dataset in QuickSight**:
    - Choose **Redshift** as the data source type.
    - Select **"Redshift manual connect"**.
    - **Data source name**: Give it a descriptive name (e.g., "DatalakeRedshift").
    - **Database server**: Use the Redshift Serverless workgroup endpoint. This can be found in the AWS Redshift console by navigating to "Workgroup configuration" for your workgroup (`RedshiftWorkgroupName` output). It will look like `your-workgroup-name.123456789012.your-region.redshift-serverless.amazonaws.com`.
    - **Port**: `5439` (default for Redshift).
    - **Database name**: `dev` (or the database name specified for `RedshiftNamespaceName`).
    - **Authentication method**: Choose **IAM** (or "IAM IDC" if using IAM Identity Center).
    - **IAM role ARN**: Provide the `QuickSightAccessRoleArn` from the stack outputs.
    - **Cluster Identifier (Workgroup Name for Serverless)**: Enter the `RedshiftWorkgroupName` from stack outputs.
    - Click **Validate connection**.
3.  **Create an Analysis**:
    - Once the dataset is created, create a new analysis using it.
    - You should be able to select schemas and tables:
        - Tables from S3 (via Glue/Lake Formation, queried by Redshift).
        - Tables from Aurora (via the Zero-ETL integration schema in Redshift).
    - You can then create visuals by dragging fields or by writing custom SQL queries against these tables within QuickSight. Example conceptual join in a custom SQL query:
      ```sql
      -- Assuming 's3_schema' for tables from S3 and 'aurora_schema' for Zero-ETL tables
      -- SELECT s.columnA, a.columnB
      -- FROM s3_schema.some_s3_table s
      -- JOIN aurora_schema.customer_details a ON s.customer_id = a.customer_id;
      ```

### Cleanup
To remove all resources created by this stack and avoid ongoing charges:
1.  Navigate to the `/app` directory.
2.  Run the CDK destroy command:
    ```bash
    cdk destroy
    ```
3.  Confirm the deletion when prompted.

**Note**:
- The S3 bucket (`this.rawDataBucket`) is configured with `removalPolicy: cdk.RemovalPolicy.DESTROY` and `autoDeleteObjects: true`, so it will be emptied and deleted upon stack destruction.
- Aurora, Redshift Serverless, and other resources will also be destroyed. Be cautious if you have important data that wasn't intended to be ephemeral.
- IAM roles and Secrets Manager secrets created by the stack will also be removed.
```
