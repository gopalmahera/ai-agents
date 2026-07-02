import { Db } from "mongodb";
export declare function mongoConfigured(): boolean;
export declare function getDb(): Promise<Db>;
export declare function mongoHealth(): Promise<boolean>;
