import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";
import mysql from 'mysql2/promise'; // Or any other MySQL client

// Configuration - replace with your actual values or use environment variables
const s3BucketName = process.env.S3_BUCKET_NAME || "YOUR_S3_BUCKET_NAME";
const auroraHost = process.env.AURORA_HOST || "YOUR_AURORA_HOST";
const auroraUser = process.env.AURORA_USER || "YOUR_AURORA_USER";
const auroraPassword = process.env.AURORA_PASSWORD || "YOUR_AURORA_PASSWORD";
const auroraDatabase = process.env.AURORA_DATABASE || "YOUR_AURORA_DATABASE";

const s3Client = new S3Client({ region: process.env.AWS_REGION || "us-east-1" });

async function seedS3() {
    console.log(`Seeding S3 bucket: ${s3BucketName}`);
    const sampleData = {
        users: [
            { id: 1, name: "Alice", email: "alice@example.com" },
            { id: 2, name: "Bob", email: "bob@example.com" },
        ],
        products: [
            { id: 101, name: "Laptop", price: 1200 },
            { id: 102, name: "Mouse", price: 25 },
        ]
    };
    const command = new PutObjectCommand({
        Bucket: s3BucketName,
        Key: "sample-data/data.json",
        Body: JSON.stringify(sampleData, null, 2),
        ContentType: "application/json"
    });

    try {
        await s3Client.send(command);
        console.log("Successfully uploaded sample data to S3.");
    } catch (error) {
        console.error("Error uploading to S3:", error);
    }
}

async function seedAurora() {
    console.log(`Seeding Aurora database: ${auroraDatabase} on host ${auroraHost}`);
    let connection;
    try {
        connection = await mysql.createConnection({
            host: auroraHost,
            user: auroraUser,
            password: auroraPassword,
            database: auroraDatabase,
        });

        console.log("Successfully connected to Aurora.");

        // Create a sample table
        await connection.execute(`
            CREATE TABLE IF NOT EXISTS customers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255)
            );
        `);
        console.log("Table 'customers' ensured to exist.");

        // Insert sample data
        const [result] = await connection.execute(
            "INSERT INTO customers (name, email) VALUES (?, ?), (?, ?)",
            ["John Doe", "john.doe@example.com", "Jane Smith", "jane.smith@example.com"]
        );
        console.log(`Successfully inserted sample data into Aurora. Rows affected: ${(result as any).affectedRows}`);

    } catch (error) {
        console.error("Error seeding Aurora:", error);
    } finally {
        if (connection) {
            await connection.end();
            console.log("Aurora connection closed.");
        }
    }
}

async function main() {
    console.log("Starting data seeding process...");
    // Check for placeholder values and warn
    if (s3BucketName === "YOUR_S3_BUCKET_NAME" || auroraHost === "YOUR_AURORA_HOST") {
        console.warn("---------------------------------------------------------------------------");
        console.warn("WARNING: Script is using placeholder values for S3/Aurora configuration.");
        console.warn("Please update environment variables or the script with actual values.");
        console.warn("---------------------------------------------------------------------------");
    }
    await seedS3();
    await seedAurora();
    console.log("Data seeding process complete.");
}

main().catch(error => {
    console.error("Unhandled error in main seeding function:", error);
});
